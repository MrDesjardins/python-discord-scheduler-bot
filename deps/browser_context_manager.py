"""Browser Context Manager to handle the browser and download the matches from the Ubisoft API"""

import json
import os
import random
import shutil
import signal
import subprocess
import tempfile
import time
from typing import List, Optional, Union

import psutil
from filelock import FileLock
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc  # type: ignore
from bs4 import BeautifulSoup
from deps.models import UserFullMatchStats, UserInformation, UserQueueForStats
from deps.log import print_error_log, print_log, print_warning_log
from deps.functions_r6_tracker import parse_json_from_full_matches, parse_json_max_rank, parse_json_user_info
from deps.functions import (
    get_url_api_ranked_matches,
    get_url_user_ranked_matches,
    get_url_api_user_info,
)
from deps.siege import siege_ranks
from deps.browser_config import BrowserConfig
from deps.browser_exceptions import (
    BrowserException,
    BrowserStartupException,
    BrowserTimeoutException,
    BrowserVersionMismatchException,
    CircuitBreakerOpenException,
)
from deps.browser_circuit_breaker import BrowserCircuitBreaker

CHROMIUM_LOCK = FileLock("/tmp/chromium.lock")
# Shared circuit breaker across all BrowserContextManager instances
_CIRCUIT_BREAKER: Optional[BrowserCircuitBreaker] = None


class BrowserContextManager:
    """
    Context manager to handle the browser
    Slow approach but works to not get the 403 error or blocked request
    It goes first to the website to get the proper cookies and then to the API
    Must not be headless to work

    Pre-requisite:
    sudo apt install -y xvfb
    Have /usr/bin/google-chrome (not /usr/bin/chromium-browser) installed
    """

    driver: Optional[uc.Chrome] = None
    default_profile: str
    counter: int
    environment: Union[str, None]
    config: BrowserConfig

    def __init__(self, default_profile: str = "noSleep_rb6", config: Optional[BrowserConfig] = None) -> None:
        self.environment = (os.getenv("ENV") or "").lower()
        self.default_profile = default_profile
        self.counter = 0
        self.driver = None
        self._lock = CHROMIUM_LOCK
        self._xvfb_proc: Optional[subprocess.Popen] = None
        self._profile_dir: Optional[str] = None
        self._lock_acquired = False
        self.config = config or BrowserConfig.from_environment()

        # Initialize global circuit breaker if needed
        global _CIRCUIT_BREAKER  # pylint: disable=global-statement
        if _CIRCUIT_BREAKER is None:
            _CIRCUIT_BREAKER = BrowserCircuitBreaker(
                failure_threshold=self.config.circuit_breaker_failure_threshold,
                success_threshold=self.config.circuit_breaker_success_threshold,
                timeout_seconds=self.config.circuit_breaker_timeout_seconds,
            )

    @staticmethod
    def get_circuit_breaker_stats() -> dict:
        """Get circuit breaker statistics for monitoring"""
        if _CIRCUIT_BREAKER:
            return _CIRCUIT_BREAKER.get_stats()
        return {}

    def _check_file_descriptor_usage(self) -> tuple[int, int]:
        """
        Check current file descriptor usage for this process.
        Returns (current_fds, max_fds)
        """
        try:
            pid = os.getpid()
            # Count open file descriptors
            fd_dir = f"/proc/{pid}/fd"
            if os.path.exists(fd_dir):
                current_fds = len(os.listdir(fd_dir))
            else:
                current_fds = 0

            # Get soft limit
            import resource  # pylint: disable=import-outside-toplevel

            soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)

            return current_fds, soft_limit
        except Exception as e:
            print_warning_log(f"Failed to check file descriptor usage: {e}")
            return 0, 0

    def _calculate_backoff(self, attempt: int, is_fd_exhaustion: bool = False) -> float:
        """
        Calculate exponential backoff with jitter.

        Args:
            attempt: Current retry attempt (0-indexed)
            is_fd_exhaustion: True if this is a file descriptor exhaustion error

        Returns:
            Backoff time in seconds
        """
        if is_fd_exhaustion:
            # Use special longer backoff for FD exhaustion
            return self.config.fd_exhaustion_backoff_seconds

        # Exponential backoff: base * (multiplier ^ attempt)
        backoff = self.config.base_backoff_seconds * (self.config.backoff_multiplier**attempt)

        # Cap at maximum
        backoff = min(backoff, self.config.max_backoff_seconds)

        # Add jitter: ± (backoff * jitter_factor)
        jitter = backoff * self.config.jitter_factor * (2 * random.random() - 1)
        backoff_with_jitter = backoff + jitter

        return max(0.1, backoff_with_jitter)  # Ensure minimum 0.1s

    def __enter__(self):
        # Check circuit breaker first
        if self.config.circuit_breaker_enabled and _CIRCUIT_BREAKER:
            if not _CIRCUIT_BREAKER.allow_request():
                stats = _CIRCUIT_BREAKER.get_stats()
                raise CircuitBreakerOpenException(
                    f"Circuit breaker is OPEN after {stats['total_failures']} failures. "
                    f"Will retry after timeout. Last failure: {stats.get('last_failure_time', 'N/A')}"
                )

        # Check file descriptor usage before starting
        current_fds, max_fds = self._check_file_descriptor_usage()
        if max_fds > 0:
            usage_percent = (current_fds / max_fds) * 100
            if usage_percent > self.config.fd_warning_threshold_percent:
                print_warning_log(
                    f"High file descriptor usage: {current_fds}/{max_fds} ({usage_percent:.1f}%). "
                    "Browser startup may fail."
                )
            elif usage_percent > self.config.fd_info_threshold_percent:
                print_log(f"File descriptor usage: {current_fds}/{max_fds} ({usage_percent:.1f}%)")

        last_exception = None

        for attempt in range(self.config.max_retries):
            try:
                self._lock.acquire(timeout=120)
                self._lock_acquired = True
                self._config_browser()

                # Success! Record with circuit breaker
                if self.config.circuit_breaker_enabled and _CIRCUIT_BREAKER:
                    _CIRCUIT_BREAKER.record_success()

                return self

            except OSError as e:
                last_exception = e
                is_fd_exhaustion = e.errno == 24  # EMFILE - Too many open files

                if is_fd_exhaustion:
                    current_fds, max_fds = self._check_file_descriptor_usage()
                    print_error_log(
                        f"Startup attempt {attempt+1}/{self.config.max_retries} failed: {e}. "
                        f"File descriptors: {current_fds}/{max_fds}"
                    )
                    self._cleanup()

                    if attempt == self.config.max_retries - 1:
                        print_error_log("Hit file descriptor limit after retries. Aborting to prevent resource exhaustion.")
                        exc = BrowserStartupException(str(e), retryable=False)
                        if self.config.circuit_breaker_enabled and _CIRCUIT_BREAKER:
                            _CIRCUIT_BREAKER.record_failure(exc)
                        raise exc

                    # Calculate backoff with special handling for FD exhaustion
                    backoff = self._calculate_backoff(attempt, is_fd_exhaustion=True)
                    print_log(f"Waiting {backoff:.1f}s before retry {attempt+2}/{self.config.max_retries}...")
                    time.sleep(backoff)
                else:
                    # Other OSError - not retryable
                    exc = BrowserStartupException(str(e), retryable=False)
                    if self.config.circuit_breaker_enabled and _CIRCUIT_BREAKER:
                        _CIRCUIT_BREAKER.record_failure(exc)
                    raise exc

            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                # Check for non-retryable errors
                is_retryable = True
                exception_to_raise = None

                if "version" in error_msg or "mismatch" in error_msg:
                    print_error_log(f"Startup attempt {attempt+1} failed with version issue: {e}")
                    print_error_log("This appears to be a Chrome/chromedriver version mismatch - retrying won't help")
                    is_retryable = False
                    exception_to_raise = BrowserVersionMismatchException(str(e))
                elif "permission" in error_msg or "access" in error_msg:
                    print_error_log(f"Startup attempt {attempt+1} failed with permission issue: {e}")
                    print_error_log("This appears to be a permissions issue - retrying won't help")
                    is_retryable = False
                    exception_to_raise = BrowserStartupException(str(e), retryable=False)
                elif "status code was: 1" in error_msg:
                    print_error_log(f"Startup attempt {attempt+1} failed: chromedriver exited with status 1")
                    print_error_log("Chromedriver failed to start - check logs above for version info and diagnostics")
                    exception_to_raise = BrowserStartupException(str(e), retryable=True)
                else:
                    print_error_log(f"Startup attempt {attempt+1}/{self.config.max_retries} failed: {e}")
                    exception_to_raise = BrowserStartupException(str(e), retryable=True)

                self._cleanup()  # Full wipe before retry

                # Don't retry if we know it won't help or if out of retries
                if not is_retryable or attempt == self.config.max_retries - 1:
                    if not is_retryable:
                        print_error_log("Error is not retryable - aborting immediately")
                    # Record failure with circuit breaker
                    if self.config.circuit_breaker_enabled and _CIRCUIT_BREAKER:
                        _CIRCUIT_BREAKER.record_failure(exception_to_raise or e)
                    raise exception_to_raise or e

                # Calculate exponential backoff with jitter
                backoff = self._calculate_backoff(attempt, is_fd_exhaustion=False)
                print_log(f"Waiting {backoff:.1f}s before retry {attempt+2}/{self.config.max_retries}...")
                time.sleep(backoff)

        # Should never reach here, but just in case
        if last_exception:
            if self.config.circuit_breaker_enabled and _CIRCUIT_BREAKER:
                _CIRCUIT_BREAKER.record_failure(last_exception)
            raise last_exception
        raise BrowserStartupException("Unknown error during browser startup")

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()

    def _wait_for_process_termination(self, pids: List[int], timeout: float) -> bool:
        """
        Wait for processes to terminate using psutil.

        Args:
            pids: List of process IDs to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            True if all processes terminated, False if timeout
        """
        if not pids:
            return True

        start_time = time.time()
        remaining_pids = set(pids)

        while time.time() - start_time < timeout:
            for pid in list(remaining_pids):
                try:
                    proc = psutil.Process(pid)
                    # Check if process is zombie or dead
                    status = proc.status()
                    if status in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                        remaining_pids.remove(pid)
                except psutil.NoSuchProcess:
                    # Process no longer exists - good!
                    remaining_pids.remove(pid)
                except Exception as e:
                    print_warning_log(f"Error checking process {pid}: {e}")
                    remaining_pids.remove(pid)  # Assume it's gone

            if not remaining_pids:
                return True

            # Only sleep if processes remain
            time.sleep(self.config.process_poll_interval_seconds)

        # Timeout - log remaining processes
        if remaining_pids:
            print_warning_log(f"Processes still alive after {timeout}s: {remaining_pids}")
        return False

    def _cleanup(self) -> None:
        print_log("Cleaning up browser and Xvfb...")

        pids_to_wait = []

        # 1. Try to quit the driver gracefully and close all its file descriptors
        if self.driver:
            try:
                # Get the PID before quitting
                browser_pid = self.driver.browser_pid
                if browser_pid:
                    pids_to_wait.append(browser_pid)

                # Close any open file descriptors the driver might have
                try:
                    if hasattr(self.driver, "service") and self.driver.service:
                        if hasattr(self.driver.service, "process") and self.driver.service.process:
                            # Collect chromedriver PID
                            if self.driver.service.process.pid:
                                pids_to_wait.append(self.driver.service.process.pid)

                            # Close subprocess pipes explicitly
                            if self.driver.service.process.stdin:
                                self.driver.service.process.stdin.close()
                            if self.driver.service.process.stdout:
                                self.driver.service.process.stdout.close()
                            if self.driver.service.process.stderr:
                                self.driver.service.process.stderr.close()
                except Exception as e:
                    print_warning_log(f"BrowserContextManager: Error closing service process pipes: {e}")

                self.driver.quit()

                # Force kill the specific browser PID just in case
                if browser_pid:
                    try:
                        os.kill(browser_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Already dead
            except Exception as e:
                print_warning_log(f"BrowserContextManager: Error during driver cleanup: {e}")
            self.driver = None

        # 2. Kill the Xvfb process group (the nuclear option)
        if self._xvfb_proc:
            try:
                # Collect all Xvfb children PIDs using psutil
                try:
                    xvfb_proc = psutil.Process(self._xvfb_proc.pid)
                    children = xvfb_proc.children(recursive=True)
                    for child in children:
                        pids_to_wait.append(child.pid)
                    pids_to_wait.append(self._xvfb_proc.pid)
                except psutil.NoSuchProcess:
                    pass  # Xvfb already dead

                # This kills the Xvfb AND any children it spawned
                xvfb_pgid = os.getpgid(self._xvfb_proc.pid)
                os.killpg(xvfb_pgid, signal.SIGKILL)
            except Exception as e:
                print_warning_log(f"BrowserContextManager: Error killing Xvfb process: {e}")
            self._xvfb_proc = None

        # 3. Wait for processes to fully terminate using psutil
        # This prevents the "cannot connect to chrome" race condition
        if pids_to_wait:
            all_terminated = self._wait_for_process_termination(
                pids_to_wait, self.config.cleanup_max_wait_seconds
            )
            if all_terminated:
                print_log("All browser processes terminated successfully")
            else:
                print_warning_log("Some processes may still be terminating after timeout")

        # 4. Final Wipe of the specific profile directory
        if self._profile_dir and os.path.exists(self._profile_dir):
            try:
                shutil.rmtree(self._profile_dir, ignore_errors=True)
                print_log(f"Deleted profile directory: {self._profile_dir}")
            except Exception as e:
                print_warning_log(f"Failed to delete profile directory {self._profile_dir}: {e}")
            self._profile_dir = None

        # 5. Always release the lock, even if cleanup partially failed
        if self._lock_acquired:
            try:
                self._lock.release()
                print_log("Released browser lock")
            except Exception as e:
                print_warning_log(f"Failed to release lock: {e}")
            self._lock_acquired = False

    def _kill_orphaned_chrome_processes(self) -> None:
        """Kill any orphaned Chrome/chromedriver processes before starting"""
        try:
            # Only do this in production to avoid interfering with developer's Chrome instances
            if self.environment == "prod":
                # Kill orphaned chrome processes
                # Note: capture_output=True returns strings, not file objects, so no .close() needed
                subprocess.run(
                    ["pkill", "-9", "-f", "google-chrome.*--remote-debugging"],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )

                subprocess.run(
                    ["pkill", "-9", "-f", "chromedriver"], check=False, capture_output=True, timeout=5
                )

                time.sleep(0.5)  # Give processes time to die
                print_log("Cleaned up any orphaned Chrome processes")

                # Clean up any leftover profile directories from previous crashes
                # Note: capture_output=True returns strings, not file objects, so no .close() needed
                subprocess.run(
                    "find /tmp -maxdepth 1 -name 'chrome_profile_*' -mmin +60 -exec rm -rf {} +",
                    shell=True,
                    check=False,
                    capture_output=True,
                    timeout=10,
                )

                time.sleep(0.5)  # Give processes time to die
        except Exception as e:
            print_log(f"Failed to kill orphaned processes (non-critical): {e}")

    def _check_chrome_environment(self) -> dict:
        """
        Verify Chrome/chromedriver environment before attempting to launch.
        Returns diagnostic information.
        """
        diagnostics = {}

        # Check Chrome binary
        chrome_path = "/usr/bin/google-chrome" if self.environment == "prod" else None
        if chrome_path:
            if os.path.exists(chrome_path) and os.access(chrome_path, os.X_OK):
                try:
                    result = subprocess.run(
                        [chrome_path, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    chrome_version = result.stdout.strip()
                    diagnostics["chrome_version"] = chrome_version

                    # Check for stderr errors
                    if result.stderr:
                        stderr_msg = result.stderr.strip()
                        if stderr_msg:
                            diagnostics["chrome_stderr"] = stderr_msg
                            print_warning_log(f"Chrome stderr: {stderr_msg}")

                    # Extract version number for comparison
                    import re
                    version_match = re.search(r'(\d+)\.', chrome_version)
                    if version_match:
                        diagnostics["chrome_major_version"] = int(version_match.group(1))
                except Exception as e:
                    diagnostics["chrome_error"] = str(e)
            else:
                diagnostics["chrome_error"] = f"Not found or not executable at {chrome_path}"

        # Check chromedriver binary
        driver_path = "/usr/bin/chromedriver" if self.environment == "prod" else "chromedriver"
        try:
            result = subprocess.run(
                [driver_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            driver_version = result.stdout.strip()
            diagnostics["chromedriver_version"] = driver_version

            # Extract version number for comparison
            import re
            version_match = re.search(r'(\d+)\.', driver_version)
            if version_match:
                diagnostics["chromedriver_major_version"] = int(version_match.group(1))

            # Capture any stderr warnings
            if result.stderr:
                stderr_msg = result.stderr.strip()
                if stderr_msg:
                    diagnostics["chromedriver_stderr"] = stderr_msg
                    print_warning_log(f"Chromedriver stderr: {stderr_msg}")
        except FileNotFoundError:
            diagnostics["chromedriver_error"] = f"chromedriver not found at {driver_path}"
        except Exception as e:
            diagnostics["chromedriver_error"] = str(e)

        # Check for version compatibility
        if "chrome_major_version" in diagnostics and "chromedriver_major_version" in diagnostics:
            chrome_ver = diagnostics["chrome_major_version"]
            driver_ver = diagnostics["chromedriver_major_version"]
            if chrome_ver != driver_ver:
                diagnostics["version_mismatch"] = True
                print_error_log(
                    f"VERSION MISMATCH: Chrome {chrome_ver} vs chromedriver {driver_ver}. "
                    f"These must match! Update chromedriver to version {chrome_ver}."
                )
            else:
                print_log(f"Chrome and chromedriver versions match: {chrome_ver}")

        # Log diagnostics
        if "chrome_version" in diagnostics or "chromedriver_version" in diagnostics:
            print_log(f"Environment check: Chrome={diagnostics.get('chrome_version', 'N/A')}, "
                     f"Chromedriver={diagnostics.get('chromedriver_version', 'N/A')}")
        if "chrome_error" in diagnostics or "chromedriver_error" in diagnostics:
            print_error_log(f"Environment issues detected: {diagnostics}")

        return diagnostics

    def _config_browser(self):
        # 1. Create a unique path for THIS instance
        # This ensures that even with the lock, we know exactly which folder to kill
        self._profile_dir = tempfile.mkdtemp(prefix="chrome_profile_", dir="/tmp")
        # Clean up any orphaned processes first
        self._kill_orphaned_chrome_processes()

        # 2. Check environment before attempting launch
        self._check_chrome_environment()

        options = uc.ChromeOptions()
        # 3. Tell Chrome to use this specific folder
        options.add_argument(f"--user-data-dir={self._profile_dir}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-setuid-sandbox")
        # Add verbose logging to help diagnose issues
        options.add_argument("--enable-logging")
        options.add_argument("--v=1")

        if self.environment == "prod":
            print_log("Launching Chrome in System-Level Xvfb environment...")
            try:
                # Create driver with verbose error capture
                self.driver = uc.Chrome(
                    options=options,
                    browser_executable_path="/usr/bin/google-chrome",  # Version 144
                    headless=False,
                    driver_executable_path="/usr/bin/chromedriver",  # Force it to use your fixed 144 driver
                )
                print_log("Driver attached successfully!")
            except Exception as e:
                # Try to capture chromedriver stderr if available
                error_details = str(e)

                # Check if we can get more info from the service
                try:
                    if hasattr(self, 'driver') and self.driver and hasattr(self.driver, 'service'):
                        service = self.driver.service
                        if hasattr(service, 'process') and service.process:
                            if service.process.stderr:
                                stderr_output = service.process.stderr.read()
                                if stderr_output:
                                    error_details += f"\nChromedriver stderr: {stderr_output}"
                except Exception as e:
                    print_warning_log(f"BrowserContextManager: Error reading chromedriver stderr: {e}")

                print_error_log(f"Failed to attach driver: {error_details}")

                # Try to run chromedriver directly to see what error it gives
                try:
                    print_log("Testing chromedriver standalone startup...")
                    test_result = subprocess.run(
                        ["/usr/bin/chromedriver", "--port=9999"],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    if test_result.returncode != 0:
                        print_error_log(f"Chromedriver exited with code {test_result.returncode}")
                    if test_result.stderr:
                        stderr_output = test_result.stderr.strip()
                        if stderr_output:
                            print_error_log(f"Chromedriver direct test stderr: {stderr_output}")
                    if test_result.stdout:
                        stdout_output = test_result.stdout.strip()
                        if stdout_output:
                            print_log(f"Chromedriver direct test stdout: {stdout_output}")
                except subprocess.TimeoutExpired:
                    # Timeout is expected if chromedriver starts successfully
                    print_log("Chromedriver can start standalone (timeout is expected - this is GOOD)")
                except Exception as test_error:
                    print_error_log(f"Chromedriver direct test failed: {test_error}")

                # Check for chromedriver log files
                try:
                    log_files = subprocess.run(
                        ["find", "/tmp", "-name", "chromedriver*.log", "-mmin", "-5"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if log_files.stdout:
                        log_paths = log_files.stdout.strip().split('\n')
                        for log_path in log_paths:
                            if log_path and os.path.exists(log_path):
                                print_log(f"Found recent chromedriver log: {log_path}")
                                try:
                                    with open(log_path, 'r') as f:
                                        last_lines = f.readlines()[-20:]  # Last 20 lines
                                        print_error_log(f"Last lines from {log_path}:\n{''.join(last_lines)}")
                                except Exception as read_err:
                                    print_warning_log(f"Could not read log file: {read_err}")
                except Exception as log_err:
                    print_warning_log(f"Could not search for chromedriver logs: {log_err}")

                raise
        else:
            # --- WSL (DEV) ---
            self.driver = uc.Chrome(
                options=options, headless=False, use_subprocess=True, port=45455  # Fixed the 454a55 typo here
            )

        self.driver.set_page_load_timeout(self.config.page_load_timeout_seconds)
        # Load initial page
        self.driver.get(get_url_user_ranked_matches(self.default_profile))

        # Only wait for app-container if you are sure it's on the landing page
        # If the landing page is just JSON, this will fail.
        # Consider wrapping this in a try/except if it causes crashes.
        try:
            WebDriverWait(self.driver, self.config.initial_page_wait_timeout_seconds).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            print_log("Initial page load wait timed out, proceeding anyway...")
        except Exception as e:
            print_warning_log(f"Initial page load encountered unexpected error: {e}, proceeding anyway...")

    def download_full_matches(self, user_queued: UserQueueForStats) -> List[UserFullMatchStats]:
        """
        Download the matches for the given Ubisoft username
        This is version 2 of download_matches. It contains a lot more fields.
        The future goal is to replace download_matches with this function.

        Raises:
            BrowserException: If Ubisoft username not provided or JSON not found
            BrowserTimeoutException: If page load times out
        """
        # # Step 1: Download the page content
        self.counter += 1
        ubisoft_user_name = user_queued.user_info.ubisoft_username_active
        if not ubisoft_user_name:
            raise BrowserException("download_matches: Ubisoft username not found.")

        api_url = get_url_api_ranked_matches(ubisoft_user_name)
        self.driver.get(api_url)
        print_log(f"download_matches: Downloading matches for {ubisoft_user_name} using {api_url}")

        # Wait until the page contains the expected JSON data
        try:
            WebDriverWait(self.driver, self.config.element_wait_timeout_seconds).until(
                EC.presence_of_element_located((By.TAG_NAME, "pre"))
            )
        except TimeoutException as e:
            raise BrowserTimeoutException(f"download_matches: Timeout waiting for JSON data: {e}") from e

        # Step 2: Extract the page content, expecting JSON
        page_source = self.driver.page_source

        # Step 3: Remove the HTML
        soup = BeautifulSoup(page_source, "html.parser")
        # Find the <pre> tag containing the JSON
        pre_tag = soup.find("pre")

        # Ensure the <pre> tag is found and contains the expected JSON data
        if not pre_tag:
            raise BrowserException("download_matches: JSON data not found within <pre> tag.")

        # Step 4: Extract the text content of the <pre> tag
        json_data = pre_tag.get_text().strip()

        try:
            # Step 5: Parse the JSON data
            data = json.loads(json_data)
            print_log(f"download_matches: JSON found for {ubisoft_user_name}")
            # Save the JSON data to a file for debugging
            if os.getenv("ENV") == "dev":
                try:
                    with open(f"r6tracker_data_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
                except Exception as e:
                    print_warning_log(f"Failed to write debug JSON file: {e}")
            # Step 6: Parse the JSON data to extract the matches
            return parse_json_from_full_matches(data, user_queued.user_info)
        except json.JSONDecodeError as e:
            raise BrowserException(f"download_matches: Error parsing JSON: {e}") from e

    def refresh_browser(self) -> None:
        """Refresh the browser"""
        self.driver.refresh()
        WebDriverWait(self.driver, 15).until(EC.visibility_of_element_located((By.ID, "app-container")))
        print_log("refresh_browser: Browser refreshed")

    def download_max_rank(self, ubisoft_user_name: Optional[str] = None) -> tuple[str, int]:
        """
        Download the web page, and extract the max rank

        Raises:
            BrowserException: If Ubisoft username not provided or JSON not found
            BrowserTimeoutException: If page load times out
        """
        rank = "Copper"
        # Step 1: Check if the Ubisoft username is provided, otherwise use the default profile
        if ubisoft_user_name is None:
            ubisoft_user_name = self.default_profile

        # Step 2: Download the page content
        self.counter += 1
        if not ubisoft_user_name:
            raise BrowserException("download_max_rank: Ubisoft username not found.")

        api_url = get_url_api_user_info(ubisoft_user_name)
        self.driver.get(api_url)
        print_log(f"download_max_rank: Downloading profile for {ubisoft_user_name} using {api_url}")

        # Wait until the page contains the expected JSON data
        try:
            WebDriverWait(self.driver, self.config.element_wait_timeout_seconds).until(
                EC.presence_of_element_located((By.TAG_NAME, "pre"))
            )
        except TimeoutException as e:
            raise BrowserTimeoutException(f"download_max_rank: Timeout waiting for JSON data: {e}") from e

        # Step 3: Extract the page content, expecting JSON
        page_source = self.driver.page_source

        # Step 4: Remove the HTML
        soup = BeautifulSoup(page_source, "html.parser")
        # Find the <pre> tag containing the JSON
        pre_tag = soup.find("pre")

        # Ensure the <pre> tag is found and contains the expected JSON data
        if not pre_tag:
            raise BrowserException("download_max_rank: JSON data not found within <pre> tag.")

        # Step 4: Extract the text content of the <pre> tag
        json_data = pre_tag.get_text().strip()

        try:
            # Step 5: Parse the JSON data
            data = json.loads(json_data)
            print_log(f"download_max_rank: JSON found for {ubisoft_user_name}")
            # Save the JSON data to a file for debugging
            if os.getenv("ENV") == "dev":
                try:
                    with open(f"r6tracker_data_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
                except Exception as e:
                    print_warning_log(f"Failed to write debug JSON file: {e}")
            # Step 6: Parse the JSON data to extract the matches
            data_json = parse_json_max_rank(data)
            return data_json
        except json.JSONDecodeError as e:
            raise BrowserException(f"download_max_rank: Error parsing JSON: {e}") from e

    def download_full_user_information(self, user_queued: UserQueueForStats) -> Union[UserInformation, None]:
        """
        Download the user stats for the given Ubisoft username

        Raises:
            BrowserException: If Ubisoft username not provided or JSON not found
            BrowserTimeoutException: If page load times out
        """
        # # Step 1: Download the page content
        self.counter += 1
        ubisoft_user_name = user_queued.user_info.ubisoft_username_active
        if not ubisoft_user_name:
            raise BrowserException("download_full_user_stats: Ubisoft username not found.")

        api_url = get_url_api_user_info(ubisoft_user_name)
        self.driver.get(api_url)
        print_log(f"download_full_user_stats: Downloading stats for {ubisoft_user_name} using {api_url}")

        # Wait until the page contains the expected JSON data
        try:
            WebDriverWait(self.driver, self.config.element_wait_timeout_seconds).until(
                EC.presence_of_element_located((By.TAG_NAME, "pre"))
            )
        except TimeoutException as e:
            raise BrowserTimeoutException(f"download_full_user_stats: Timeout waiting for JSON data: {e}") from e

        # Step 2: Extract the page content, expecting JSON
        page_source = self.driver.page_source

        # Step 3: Remove the HTML
        soup = BeautifulSoup(page_source, "html.parser")
        # Find the <pre> tag containing the JSON
        pre_tag = soup.find("pre")

        # Ensure the <pre> tag is found and contains the expected JSON data
        if not pre_tag:
            raise BrowserException("download_full_user_stats: JSON data not found within <pre> tag.")

        # Step 4: Extract the text content of the <pre> tag
        json_data = pre_tag.get_text().strip()

        try:
            # Step 5: Parse the JSON data
            data = json.loads(json_data)
            print_log(f"download_full_user_stats: JSON found for {ubisoft_user_name}")
            # Save the JSON data to a file for debugging
            if os.getenv("ENV") == "dev":
                try:
                    with open(f"r6tracker_data_full_user_stats_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
                except Exception as e:
                    print_warning_log(f"Failed to write debug JSON file: {e}")
            # Step 6: Parse the JSON data to extract the matches
            return parse_json_user_info(user_queued.user_info.id, data)
        except json.JSONDecodeError as e:
            raise BrowserException(f"download_full_user_stats: Error parsing JSON: {e}") from e

    def download_operator_stats(self, r6_tracker_user_uuid: str) -> Optional[List]:
        """
        Download operator statistics for a given R6 Tracker user UUID.

        Args:
            r6_tracker_user_uuid: R6 Tracker UUID for the user

        Returns:
            List of operator stat dictionaries

        Raises:
            BrowserException: If UUID not provided or JSON not found/invalid
            BrowserTimeoutException: If page load times out
        """
        self.counter += 1

        if not r6_tracker_user_uuid:
            raise BrowserException("download_operator_stats: R6 Tracker UUID not provided.")

        # Construct API URL
        api_url = f"https://api.tracker.gg/api/v2/r6siege/standard/profile/ubi/{r6_tracker_user_uuid}/segments/operator?sessionType=ranked&season=all"

        self.driver.get(api_url)
        print_log(f"download_operator_stats: Downloading operator stats using {api_url}")

        # Wait until the page contains the expected JSON data
        try:
            WebDriverWait(self.driver, self.config.element_wait_timeout_seconds).until(
                EC.presence_of_element_located((By.TAG_NAME, "pre"))
            )
        except TimeoutException as e:
            raise BrowserTimeoutException(f"download_operator_stats: Timeout waiting for JSON data: {e}") from e

        # Get the page source
        page_source = self.driver.page_source

        # Remove the HTML
        soup = BeautifulSoup(page_source, "html.parser")
        pre_tag = soup.find("pre")

        if not pre_tag:
            raise BrowserException("download_operator_stats: JSON data not found within <pre> tag.")

        # Extract the text content of the <pre> tag
        json_data = pre_tag.get_text().strip()

        try:
            # Parse the JSON data
            data = json.loads(json_data)
            print_log(f"download_operator_stats: JSON found for UUID {r6_tracker_user_uuid}")

            # Save the JSON data to a file for debugging in dev
            if os.getenv("ENV") == "dev":
                try:
                    with open(f"r6tracker_operator_stats_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
                except Exception as e:
                    print_warning_log(f"Failed to write debug JSON file: {e}")

            return data

        except json.JSONDecodeError as e:
            raise BrowserException(f"download_operator_stats: Error parsing JSON: {e}") from e
