"""Browser Context Manager to handle the browser and download the matches from the Ubisoft API"""

import json
import os
import random
import re
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Any, List, Optional, Union

import psutil
from filelock import FileLock, Timeout as FileLockTimeout
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc  # type: ignore
from bs4 import BeautifulSoup
from deps.models import UserFullMatchStats, UserInformation, UserQueueForStats
from deps.log import print_error_log, print_log, print_warning_log
from deps.functions_r6_tracker import (
    parse_json_current_season_rank,
    parse_json_from_full_matches,
    parse_json_max_rank,
    parse_json_user_info,
)
from deps.functions import (
    get_url_api_ranked_matches,
    get_url_api_user_info,
    get_url_user_profile_main,
)
from deps.siege import siege_ranks
from deps.browser_config import BrowserConfig
from deps.browser_exceptions import (
    BrowserException,
    BrowserLockContentionException,
    BrowserStartupException,
    BrowserTimeoutException,
    BrowserVersionMismatchException,
    CircuitBreakerOpenException,
)
from deps.browser_circuit_breaker import BrowserCircuitBreaker

CHROMIUM_LOCK = FileLock("/tmp/chromium.lock")
# Shared circuit breaker across all BrowserContextManager instances
_CIRCUIT_BREAKER: Optional[BrowserCircuitBreaker] = None

_CHROME_BINARY_CANDIDATES = (
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
)


def detect_chrome_major_version(chrome_paths: Optional[List[str]] = None) -> Optional[int]:
    """
    Return the installed Chrome major version (e.g. 145), or None if it cannot be detected.
    Override with CHROME_VERSION_MAIN when auto-detection is wrong.
    """
    env_override = os.getenv("CHROME_VERSION_MAIN", "").strip()
    if env_override:
        try:
            return int(env_override)
        except ValueError:
            print_warning_log(f"Invalid CHROME_VERSION_MAIN={env_override!r}; falling back to auto-detect.")

    paths = chrome_paths if chrome_paths is not None else list(_CHROME_BINARY_CANDIDATES)
    for chrome_path in paths:
        if not os.path.exists(chrome_path) or not os.access(chrome_path, os.X_OK):
            continue
        try:
            result = subprocess.run([chrome_path, "--version"], capture_output=True, text=True, timeout=5)
            version_line = (result.stdout or result.stderr or "").strip()
            version_match = re.search(r"(\d+)\.", version_line)
            if version_match:
                return int(version_match.group(1))
        except Exception as e:
            print_warning_log(f"Could not read Chrome version from {chrome_path}: {e}")
    return None


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

    def _active_driver(self) -> uc.Chrome:
        if self.driver is None:
            raise BrowserException("Browser driver is not initialized.")
        return self.driver

    def _is_cloudflare_challenge(self) -> bool:
        """Detect the challenge page that otherwise looks like a generic JSON timeout."""
        driver = self._active_driver()
        try:
            title = (driver.title or "").lower()
            source = (driver.page_source or "")[:200_000].lower()
        except Exception:
            return False

        # The API returns a Cloudflare HTML challenge instead of <pre> JSON. Detecting it
        # lets us click the Turnstile checkbox and preserve the clearance cookie in the profile.
        return any(
            marker in title or marker in source
            for marker in ("just a moment", "verify you are human", "cf-mitigated", "cloudflare")
        )

    @staticmethod
    def _find_cf_iframe_backend_id(node: dict) -> Optional[int]:
        """Depth-first search of a CDP DOM tree for the Cloudflare challenge iframe."""
        if node.get("nodeName") == "IFRAME":
            attrs = node.get("attributes", [])
            attr_pairs = dict(zip(attrs[::2], attrs[1::2]))
            if "challenges.cloudflare.com" in attr_pairs.get("src", ""):
                return node.get("backendNodeId")
        for key in ("children", "contentDocument", "shadowRoots"):
            value = node.get(key)
            candidates = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
            for candidate in candidates:
                found = BrowserContextManager._find_cf_iframe_backend_id(candidate)
                if found is not None:
                    return found
        return None

    def _find_cloudflare_widget_rect(self) -> Optional[dict]:
        """
        Return the viewport rectangle of the Cloudflare "verify you are human" widget.

        The checkbox lives in a cross-origin iframe nested in a *closed* shadow root,
        so it is invisible to document.querySelectorAll. CDP's DOM.getDocument with
        pierce=true walks through closed shadow roots and iframe documents.
        """
        driver = self._active_driver()
        try:
            document = driver.execute_cdp_cmd("DOM.getDocument", {"depth": -1, "pierce": True})
            backend_id = self._find_cf_iframe_backend_id(document["root"])
            if backend_id is None:
                return None
            box = driver.execute_cdp_cmd("DOM.getBoxModel", {"backendNodeId": backend_id})
            content = box["model"]["content"]  # x1,y1, x2,y2, x3,y3, x4,y4
        except Exception as e:
            print_warning_log(f"_find_cloudflare_widget_rect: {e}")
            return None
        rect = {
            "x": content[0],
            "y": content[1],
            "width": content[2] - content[0],
            "height": content[5] - content[1],
        }
        if rect["width"] < 10 or rect["height"] < 10:
            return None
        return rect

    def _cdp_trusted_click(self, x: float, y: float) -> None:
        """
        Click at viewport coordinates using CDP input events.

        CDP-dispatched mouse events carry isTrusted=true, which the Cloudflare
        Turnstile checkbox requires; synthetic DOM events would be ignored.
        """
        driver = self._active_driver()
        driver.execute_cdp_cmd(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": x, "y": y},
        )
        time.sleep(0.05 + random.random() * 0.15)
        for event_type in ("mousePressed", "mouseReleased"):
            driver.execute_cdp_cmd(
                "Input.dispatchMouseEvent",
                {"type": event_type, "x": x, "y": y, "button": "left", "clickCount": 1},
            )
            time.sleep(0.04 + random.random() * 0.08)

    def _json_is_ready(self) -> bool:
        driver = self._active_driver()
        try:
            return bool(driver.find_elements(By.TAG_NAME, "pre"))
        except Exception:
            return False

    def _attempt_cloudflare_solve(self, log_name: str) -> bool:
        """
        Poll the challenge page and click the Turnstile checkbox until the API JSON
        appears or the budget runs out. Returns True if the JSON is ready.
        """
        budget = self.config.cloudflare_auto_solve_seconds
        if budget <= 0:
            return self._json_is_ready()

        print_warning_log(f"{log_name}: Cloudflare challenge detected; attempting automatic checkbox solve.")
        deadline = time.time() + budget
        while time.time() < deadline:
            if self._json_is_ready():
                print_log(f"{log_name}: Cloudflare challenge cleared.")
                return True
            if not self._is_cloudflare_challenge():
                # Challenge gone but JSON not rendered yet; give the reload a moment.
                time.sleep(1.5)
                continue
            rect = self._find_cloudflare_widget_rect()
            if rect is not None:
                # The checkbox sits near the left edge, vertically centred in the widget.
                click_x = rect["x"] + 30
                click_y = rect["y"] + rect["height"] / 2
                time.sleep(0.2 + random.random() * 0.6)
                try:
                    self._cdp_trusted_click(click_x, click_y)
                    print_log(f"{log_name}: Clicked Cloudflare checkbox at ({click_x:.0f}, {click_y:.0f}).")
                except Exception as e:
                    print_warning_log(f"{log_name}: Cloudflare checkbox click failed: {e}")
            time.sleep(3.0)
        return self._json_is_ready()

    def _wait_for_json(self, log_name: str) -> None:
        """Wait for the API JSON, solving a Cloudflare challenge automatically if one appears."""
        driver = self._active_driver()

        if self._is_cloudflare_challenge():
            if not self._attempt_cloudflare_solve(log_name):
                # Optional last-resort window for a human watching the live browser.
                manual_wait = self.config.cloudflare_manual_wait_seconds
                if manual_wait > 0:
                    print_warning_log(f"{log_name}: Auto-solve failed. Waiting {manual_wait}s for manual completion.")
                    try:
                        WebDriverWait(driver, manual_wait).until(lambda d: bool(d.find_elements(By.TAG_NAME, "pre")))
                    except TimeoutException as e:
                        raise BrowserTimeoutException(
                            f"{log_name}: Cloudflare challenge was not cleared; no JSON response received"
                        ) from e
                    return
                raise BrowserTimeoutException(
                    f"{log_name}: Cloudflare challenge was not cleared; no JSON response received"
                )
            return

        try:
            WebDriverWait(driver, self.config.element_wait_timeout_seconds).until(
                lambda current_driver: bool(current_driver.find_elements(By.TAG_NAME, "pre"))
            )
        except TimeoutException as e:
            if self._is_cloudflare_challenge():
                if self._attempt_cloudflare_solve(log_name):
                    return
                raise BrowserTimeoutException(
                    f"{log_name}: Cloudflare challenge was not cleared; no JSON response received"
                ) from e
            raise BrowserTimeoutException(f"{log_name}: Timeout waiting for JSON data: {e}") from e

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
                    f"Circuit breaker is OPEN after {stats['consecutive_failures']} consecutive failures. "
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

            except FileLockTimeout as e:
                # Another task is holding the browser lock (e.g., a bulk stats download).
                # This is contention, not a browser health problem: do not record a
                # circuit breaker failure and do not retry here since the holder can
                # keep the lock for minutes. The caller retries on its next cycle.
                raise BrowserLockContentionException(f"Browser lock is held by another task (waited 120s): {e}") from e
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
                        print_error_log(
                            "Hit file descriptor limit after retries. Aborting to prevent resource exhaustion."
                        )
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

                # A persistent profile that crashes Chrome on startup will keep crashing;
                # wipe it so the next attempt (and future runs) start from a clean profile.
                if is_retryable and self._looks_like_corrupt_profile_error(error_msg):
                    self._wipe_persistent_profile()

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

                # With a persistent profile, let Chrome finish flushing its user-data-dir
                # before force-killing it: a SIGKILL mid-write corrupts the profile and
                # makes every later launch crash. Only escalate if it overstays.
                persistent_profile = bool(os.getenv("BROWSER_PROFILE_DIR", "").strip())
                if browser_pid:
                    if persistent_profile:
                        self._wait_for_process_termination([browser_pid], self.config.cleanup_max_wait_seconds)
                    try:
                        os.kill(browser_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Already dead (expected for a clean quit)
            except Exception as e:
                print_warning_log(f"BrowserContextManager: Error during driver cleanup: {e}")
            self.driver = None
            self._reap_zombie_children()

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
            all_terminated = self._wait_for_process_termination(pids_to_wait, self.config.cleanup_max_wait_seconds)
            if all_terminated:
                print_log("All browser processes terminated successfully")
            else:
                print_warning_log("Some processes may still be terminating after timeout")

        # 4. Final Wipe of the specific profile directory
        profile_is_temporary = not os.getenv("BROWSER_PROFILE_DIR", "").strip()
        if self._profile_dir and os.path.exists(self._profile_dir) and profile_is_temporary:
            try:
                shutil.rmtree(self._profile_dir, ignore_errors=True)
                print_log(f"Deleted profile directory: {self._profile_dir}")
            except Exception as e:
                print_warning_log(f"Failed to delete profile directory {self._profile_dir}: {e}")
            self._profile_dir = None
        elif self._profile_dir:
            print_log(f"Preserved persistent Chrome profile: {self._profile_dir}")

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
                # Ask orphaned processes to exit cleanly first (SIGTERM), then wait, then
                # SIGKILL survivors. A blunt SIGKILL can catch a still-shutting-down Chrome
                # mid-write and corrupt a persistent profile.
                patterns = ("google-chrome.*--remote-debugging", "chromedriver")
                for pattern in patterns:
                    subprocess.run(["pkill", "-f", pattern], check=False, capture_output=True, timeout=5)
                time.sleep(1.0)
                for pattern in patterns:
                    subprocess.run(["pkill", "-9", "-f", pattern], check=False, capture_output=True, timeout=5)

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

    def _reap_zombie_children(self) -> None:
        """
        Reap defunct chromedriver/chrome children of this process.

        undetected-chromedriver does not always wait() on the chromedriver it
        spawns, leaving zombies that slowly consume PID slots over days of uptime.
        """
        try:
            children = psutil.Process(os.getpid()).children(recursive=False)
        except psutil.Error:
            return
        for child in children:
            pid = child.pid
            try:
                # A true zombie raises ZombieProcess from name()/status(); either way
                # we know its pid and can reap it. Non-zombie children are left alone.
                if child.status() != psutil.STATUS_ZOMBIE:
                    continue
            except psutil.ZombieProcess:
                pass
            except psutil.Error:
                continue
            try:
                os.waitpid(pid, os.WNOHANG)
            except (ChildProcessError, OSError):
                continue

    def _clear_stale_profile_locks(self) -> None:
        """Remove Chrome's Singleton* lock files left behind by an unclean shutdown."""
        if not self._profile_dir:
            return
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            path = os.path.join(self._profile_dir, name)
            try:
                os.unlink(path)
                print_log(f"Removed stale profile lock: {path}")
            except FileNotFoundError:
                pass
            except OSError as e:
                print_warning_log(f"Could not remove stale profile lock {path}: {e}")

    def _wipe_persistent_profile(self) -> None:
        """
        Delete a corrupted persistent profile so the next launch recreates it.

        A profile left in an inconsistent state by a mid-write SIGKILL can crash
        Chrome on startup indefinitely; the Cloudflare clearance cookie is
        re-acquired automatically, so wiping is the safe recovery.
        """
        configured_profile = os.getenv("BROWSER_PROFILE_DIR", "").strip()
        if not configured_profile or not self._profile_dir or not os.path.exists(self._profile_dir):
            return
        try:
            shutil.rmtree(self._profile_dir, ignore_errors=True)
            print_warning_log(f"Wiped corrupted persistent Chrome profile: {self._profile_dir}")
        except Exception as e:
            print_warning_log(f"Failed to wipe persistent Chrome profile {self._profile_dir}: {e}")

    @staticmethod
    def _looks_like_corrupt_profile_error(error_msg: str) -> bool:
        """True when a startup error is consistent with a broken user-data-dir."""
        lowered = error_msg.lower()
        return any(
            marker in lowered
            for marker in (
                "cannot connect to chrome",
                "chrome not reachable",
                "session not created",
                "devtoolsactiveport",
                "crashed",
                "tab crashed",
            )
        )

    def _check_chrome_environment(self) -> dict[str, Any]:
        """
        Verify Chrome/chromedriver environment before attempting to launch.
        Returns diagnostic information.
        """
        diagnostics: dict[str, Any] = {}

        # Check Chrome binary
        chrome_paths = ["/usr/bin/google-chrome"] if self.environment == "prod" else list(_CHROME_BINARY_CANDIDATES)
        chrome_major_version = detect_chrome_major_version(chrome_paths)
        if chrome_major_version is not None:
            diagnostics["chrome_major_version"] = chrome_major_version
            diagnostics["chrome_version"] = f"major {chrome_major_version}"
        else:
            diagnostics["chrome_error"] = f"Not found or not executable in {chrome_paths}"

        # Check chromedriver binary
        driver_path = "/usr/bin/chromedriver" if self.environment == "prod" else "chromedriver"
        try:
            result = subprocess.run([driver_path, "--version"], capture_output=True, text=True, timeout=5)
            driver_version = result.stdout.strip()
            diagnostics["chromedriver_version"] = driver_version

            version_match = re.search(r"(\d+)\.", driver_version)
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
            print_log(
                f"Environment check: Chrome={diagnostics.get('chrome_version', 'N/A')}, "
                f"Chromedriver={diagnostics.get('chromedriver_version', 'N/A')}"
            )
        if "chrome_error" in diagnostics or "chromedriver_error" in diagnostics:
            print_error_log(f"Environment issues detected: {diagnostics}")

        return diagnostics

    def _config_browser(self):
        # Keep the clearance cookie across batches/restarts when configured. The old temporary
        # profile made manual Cloudflare validation useless because cleanup deleted the cookie.
        configured_profile = os.getenv("BROWSER_PROFILE_DIR", "").strip()
        if configured_profile:
            self._profile_dir = os.path.abspath(os.path.expanduser(configured_profile))
            os.makedirs(self._profile_dir, exist_ok=True)
            print_log(f"Using persistent Chrome profile: {self._profile_dir}")
        else:
            self._profile_dir = tempfile.mkdtemp(prefix="chrome_profile_", dir="/tmp")
        # Clean up any orphaned processes first
        self._kill_orphaned_chrome_processes()
        # A hard-killed Chrome leaves Singleton* lock files behind; with a persistent
        # profile these block every future launch ("cannot connect to chrome").
        self._clear_stale_profile_locks()

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
        # Tracker warm-up pages are heavy; we only need the DOM/cookies, not every asset.
        options.page_load_strategy = "eager"

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
                    if hasattr(self, "driver") and self.driver and hasattr(self.driver, "service"):
                        service = self.driver.service
                        if hasattr(service, "process") and service.process:
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
                        ["/usr/bin/chromedriver", "--port=9999"], capture_output=True, text=True, timeout=3
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
                        timeout=5,
                    )
                    if log_files.stdout:
                        log_paths = log_files.stdout.strip().split("\n")
                        for log_path in log_paths:
                            if log_path and os.path.exists(log_path):
                                print_log(f"Found recent chromedriver log: {log_path}")
                                try:
                                    with open(log_path, "r") as f:
                                        last_lines = f.readlines()[-20:]  # Last 20 lines
                                        print_error_log(f"Last lines from {log_path}:\n{''.join(last_lines)}")
                                except Exception as read_err:
                                    print_warning_log(f"Could not read log file: {read_err}")
                except Exception as log_err:
                    print_warning_log(f"Could not search for chromedriver logs: {log_err}")

                raise
        else:
            # --- WSL (DEV) ---
            chrome_major_version = detect_chrome_major_version()
            chrome_kwargs: dict[str, Any] = {
                "options": options,
                "headless": False,
                "use_subprocess": True,
                "port": 45455,
            }
            if chrome_major_version is not None:
                chrome_kwargs["version_main"] = chrome_major_version
                print_log(f"Launching Chrome with chromedriver for major version {chrome_major_version}.")
            else:
                print_warning_log(
                    "Could not detect Chrome version; chromedriver may not match. "
                    "Set CHROME_VERSION_MAIN (e.g. 145) or update Google Chrome."
                )
            self.driver = uc.Chrome(**chrome_kwargs)

        driver = self._active_driver()
        driver.set_page_load_timeout(self.config.page_load_timeout_seconds)
        warmup_url = get_url_user_profile_main(self.default_profile)
        try:
            driver.get(warmup_url)
        except TimeoutException as e:
            # The browser process is healthy at this point; a slow warm-up page should not be
            # treated as a fatal startup error because later API requests may still succeed.
            print_warning_log(f"Warm-up navigation timed out for {warmup_url}: {e}")
            try:
                driver.execute_script("window.stop();")
            except Exception as stop_error:
                print_warning_log(f"Failed to stop warm-up page load cleanly: {stop_error}")

            try:
                print_warning_log(f"Warm-up page diagnostic: url={driver.current_url!r}, title={driver.title!r}")
            except Exception as diagnostic_error:
                print_warning_log(f"Failed to collect warm-up diagnostics: {diagnostic_error}")

        # Only wait for app-container if you are sure it's on the landing page
        # If the landing page is just JSON, this will fail.
        # Consider wrapping this in a try/except if it causes crashes.
        try:
            WebDriverWait(driver, self.config.initial_page_wait_timeout_seconds).until(
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
        driver = self._active_driver()
        driver.get(api_url)
        print_log(f"download_matches: Downloading matches for {ubisoft_user_name} using {api_url}")

        # Wait until the page contains the expected JSON data
        self._wait_for_json("download_matches")

        # Step 2: Extract the page content, expecting JSON
        page_source = driver.page_source

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
        driver = self._active_driver()
        driver.refresh()
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.ID, "app-container")))
        print_log("refresh_browser: Browser refreshed")

    def _download_rank_from_profile(
        self,
        ubisoft_user_name: Optional[str],
        parser,
        log_name: str,
    ) -> tuple[str, int]:
        """
        Download the profile JSON and parse a rank tuple.

        Raises:
            BrowserException: If Ubisoft username not provided or JSON not found
            BrowserTimeoutException: If page load times out
        """
        if ubisoft_user_name is None:
            ubisoft_user_name = self.default_profile

        self.counter += 1
        if not ubisoft_user_name:
            raise BrowserException(f"{log_name}: Ubisoft username not found.")

        api_url = get_url_api_user_info(ubisoft_user_name)
        driver = self._active_driver()
        driver.get(api_url)
        print_log(f"{log_name}: Downloading profile for {ubisoft_user_name} using {api_url}")

        self._wait_for_json(log_name)

        page_source = driver.page_source

        soup = BeautifulSoup(page_source, "html.parser")
        pre_tag = soup.find("pre")

        if not pre_tag:
            raise BrowserException(f"{log_name}: JSON data not found within <pre> tag.")

        json_data = pre_tag.get_text().strip()

        try:
            data = json.loads(json_data)
            print_log(f"{log_name}: JSON found for {ubisoft_user_name}")
            if os.getenv("ENV") == "dev":
                try:
                    with open(f"r6tracker_data_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
                except Exception as e:
                    print_warning_log(f"Failed to write debug JSON file: {e}")
            return parser(data)
        except json.JSONDecodeError as e:
            raise BrowserException(f"{log_name}: Error parsing JSON: {e}") from e

    def download_max_rank(self, ubisoft_user_name: Optional[str] = None) -> tuple[str, int]:
        """Download the web page, and extract the max rank."""
        return self._download_rank_from_profile(ubisoft_user_name, parse_json_max_rank, "download_max_rank")

    def download_current_season_rank(self, ubisoft_user_name: Optional[str] = None) -> tuple[str, int]:
        """Download the profile API JSON and extract the current ranked season rank."""
        return self._download_rank_from_profile(
            ubisoft_user_name,
            parse_json_current_season_rank,
            "download_current_season_rank",
        )

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
        driver = self._active_driver()
        driver.get(api_url)
        print_log(f"download_full_user_stats: Downloading stats for {ubisoft_user_name} using {api_url}")

        # Wait until the page contains the expected JSON data
        self._wait_for_json("download_full_user_stats")

        # Step 2: Extract the page content, expecting JSON
        page_source = driver.page_source

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

    def download_operator_stats(self, r6_tracker_user_uuid: str) -> Optional[dict[str, Any]]:
        """
        Download operator statistics for a given R6 Tracker user UUID.

        Args:
            r6_tracker_user_uuid: R6 Tracker UUID for the user

        Returns:
            Parsed API JSON (dict), or None if invalid

        Raises:
            BrowserException: If UUID not provided or JSON not found/invalid
            BrowserTimeoutException: If page load times out
        """
        self.counter += 1

        if not r6_tracker_user_uuid:
            raise BrowserException("download_operator_stats: R6 Tracker UUID not provided.")

        # Construct API URL
        api_url = f"https://api.tracker.gg/api/v2/r6siege/standard/profile/ubi/{r6_tracker_user_uuid}/segments/operator?sessionType=ranked&season=all"

        driver = self._active_driver()
        driver.get(api_url)
        print_log(f"download_operator_stats: Downloading operator stats using {api_url}")

        # Wait until the page contains the expected JSON data
        self._wait_for_json("download_operator_stats")

        # Get the page source
        page_source = driver.page_source

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
