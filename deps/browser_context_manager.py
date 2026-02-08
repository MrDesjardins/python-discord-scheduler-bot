"""Browser Context Manager to handle the browser and download the matches from the Ubisoft API"""

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from typing import List, Optional, Union

from filelock import FileLock
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

CHROMIUM_LOCK = FileLock("/tmp/chromium.lock")


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

    def __init__(self, default_profile: str = "noSleep_rb6") -> None:
        self.environment = (os.getenv("ENV") or "").lower()
        self.default_profile = default_profile
        self.counter = 0
        self.driver = None
        self._lock = CHROMIUM_LOCK
        self._xvfb_proc: Optional[subprocess.Popen] = None
        self._profile_dir: Optional[str] = None
        self._lock_acquired = False

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

    def __enter__(self):
        # Check file descriptor usage before starting
        current_fds, max_fds = self._check_file_descriptor_usage()
        if max_fds > 0:
            usage_percent = (current_fds / max_fds) * 100
            if usage_percent > 80:
                print_warning_log(
                    f"High file descriptor usage: {current_fds}/{max_fds} ({usage_percent:.1f}%). "
                    "Browser startup may fail."
                )
            elif usage_percent > 50:
                print_log(f"File descriptor usage: {current_fds}/{max_fds} ({usage_percent:.1f}%)")

        retries = 2
        for i in range(retries):
            try:
                self._lock.acquire(timeout=120)
                self._lock_acquired = True
                self._config_browser()
                return self
            except OSError as e:
                # If we hit file descriptor limit, don't retry immediately
                if e.errno == 24:  # EMFILE - Too many open files
                    current_fds, max_fds = self._check_file_descriptor_usage()
                    print_error_log(f"Startup attempt {i+1} failed: {e}. " f"File descriptors: {current_fds}/{max_fds}")
                    self._cleanup()
                    if i == retries - 1:
                        print_error_log(
                            "Hit file descriptor limit after retries. " "Aborting to prevent resource exhaustion."
                        )
                        raise
                    # Wait longer before retry to let system clean up
                    print_log("Waiting 10 seconds for file descriptors to be released...")
                    time.sleep(10)
                else:
                    raise
            except Exception as e:
                print_error_log(f"Startup attempt {i+1} failed: {e}")
                self._cleanup()  # Full wipe before retry
                if i == retries - 1:
                    raise
                time.sleep(2)  # Breath before retry

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()

    def _cleanup(self) -> None:
        print_log("Cleaning up browser and Xvfb...")

        browser_pid = None
        xvfb_pgid = None

        # 1. Try to quit the driver gracefully and close all its file descriptors
        if self.driver:
            try:
                # Get the PID before quitting
                browser_pid = self.driver.browser_pid

                # Close any open file descriptors the driver might have
                try:
                    if hasattr(self.driver, "service") and self.driver.service:
                        if hasattr(self.driver.service, "process") and self.driver.service.process:
                            # Close subprocess pipes explicitly
                            if self.driver.service.process.stdin:
                                self.driver.service.process.stdin.close()
                            if self.driver.service.process.stdout:
                                self.driver.service.process.stdout.close()
                            if self.driver.service.process.stderr:
                                self.driver.service.process.stderr.close()
                except:
                    pass

                self.driver.quit()
                # Force kill the specific browser PID just in case
                try:
                    os.kill(browser_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Already dead
            except:
                pass
            self.driver = None

        # 2. Kill the Xvfb process group (the nuclear option)
        if self._xvfb_proc:
            try:
                # This kills the Xvfb AND any children it spawned
                xvfb_pgid = os.getpgid(self._xvfb_proc.pid)
                os.killpg(xvfb_pgid, signal.SIGKILL)
            except:
                pass
            self._xvfb_proc = None

        # 3. Wait for processes to fully terminate
        # This prevents the "cannot connect to chrome" race condition
        max_wait = 3.0  # seconds
        start_time = time.time()
        while time.time() - start_time < max_wait:
            all_dead = True

            # Check if browser process is dead
            if browser_pid:
                try:
                    os.kill(browser_pid, 0)  # Check if process exists
                    all_dead = False
                except ProcessLookupError:
                    browser_pid = None  # Confirmed dead

            # Check if Xvfb process group is dead
            if xvfb_pgid:
                try:
                    os.killpg(xvfb_pgid, 0)  # Check if process group exists
                    all_dead = False
                except ProcessLookupError:
                    xvfb_pgid = None  # Confirmed dead

            if all_dead:
                print_log("All browser processes terminated successfully")
                break

            time.sleep(0.1)  # Small delay between checks

        if browser_pid or xvfb_pgid:
            print_warning_log(
                f"Some processes may still be terminating (browser_pid={browser_pid}, xvfb_pgid={xvfb_pgid})"
            )

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
                # Kill orphaned chrome processes - explicitly close subprocess handles
                result1 = subprocess.run(
                    ["pkill", "-9", "-f", "google-chrome.*--remote-debugging"],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
                if result1.stdout:
                    result1.stdout.close()
                if result1.stderr:
                    result1.stderr.close()

                result2 = subprocess.run(
                    ["pkill", "-9", "-f", "chromedriver"], check=False, capture_output=True, timeout=5
                )
                if result2.stdout:
                    result2.stdout.close()
                if result2.stderr:
                    result2.stderr.close()

                time.sleep(0.5)  # Give processes time to die
                print_log("Cleaned up any orphaned Chrome processes")

                # Clean up any leftover profile directories from previous crashes
                result3 = subprocess.run(
                    "find /tmp -maxdepth 1 -name 'chrome_profile_*' -mmin +60 -exec rm -rf {} +",
                    shell=True,
                    check=False,
                    capture_output=True,
                    timeout=10,
                )
                if result3.stdout:
                    result3.stdout.close()
                if result3.stderr:
                    result3.stderr.close()

                time.sleep(0.5)  # Give processes time to die
        except Exception as e:
            print_log(f"Failed to kill orphaned processes (non-critical): {e}")

    def _config_browser(self):
        # 1. Create a unique path for THIS instance
        # This ensures that even with the lock, we know exactly which folder to kill
        self._profile_dir = tempfile.mkdtemp(prefix="chrome_profile_", dir="/tmp")
        # Clean up any orphaned processes first
        self._kill_orphaned_chrome_processes()

        options = uc.ChromeOptions()
        # 2. Tell Chrome to use this specific folder
        options.add_argument(f"--user-data-dir={self._profile_dir}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-setuid-sandbox")

        if self.environment == "prod":
            print_log("Launching Chrome in System-Level Xvfb environment...")
            try:
                self.driver = uc.Chrome(
                    options=options,
                    browser_executable_path="/usr/bin/google-chrome",  # Version 144
                    headless=False,
                    driver_executable_path="/usr/bin/chromedriver",  # Force it to use your fixed 144 driver
                )
                print_log("Driver attached successfully!")
            except Exception as e:
                print_log(f"Failed to attach driver: {e}")
                raise
        else:
            # --- WSL (DEV) ---
            self.driver = uc.Chrome(
                options=options, headless=False, use_subprocess=True, port=45455  # Fixed the 454a55 typo here
            )

        self.driver.set_page_load_timeout(60)
        # Load initial page
        self.driver.get(get_url_user_ranked_matches(self.default_profile))

        # Only wait for app-container if you are sure it's on the landing page
        # If the landing page is just JSON, this will fail.
        # Consider wrapping this in a try/except if it causes crashes.
        try:
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except:
            print_log("Initial page load wait timed out, proceeding anyway...")

    def download_full_matches(self, user_queued: UserQueueForStats) -> List[UserFullMatchStats]:
        """
        Download the matches for the given Ubisoft username
        This is version 2 of download_matches. It contains a lot more fields.
        The future goal is to replace download_matches with this function.
        """
        # # Step 1: Download the page content
        self.counter += 1
        ubisoft_user_name = user_queued.user_info.ubisoft_username_active
        if not ubisoft_user_name:
            print_error_log("download_matches: Ubisoft username not found.")
            return []
        api_url = get_url_api_ranked_matches(ubisoft_user_name)
        self.driver.get(api_url)
        print_log(f"download_matches: Downloading matches for {ubisoft_user_name} using {api_url}")
        # Wait until the page contains the expected JSON data
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "pre")))

        # Step 2: Extract the page content, expecting JSON
        page_source = self.driver.page_source

        # Step 3: Remove the HTML
        soup = BeautifulSoup(page_source, "html.parser")
        # Find the <pre> tag containing the JSON
        pre_tag = soup.find("pre")

        # Ensure the <pre> tag is found and contains the expected JSON data
        if pre_tag:
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
                print_error_log(f"download_matches: Error parsing JSON: {e}")
        else:
            print_error_log("download_matches: JSON data not found within <pre> tag.")
        return []

    def refresh_browser(self) -> None:
        """Refresh the browser"""
        self.driver.refresh()
        WebDriverWait(self.driver, 15).until(EC.visibility_of_element_located((By.ID, "app-container")))
        print_log("refresh_browser: Browser refreshed")

    def download_max_rank(self, ubisoft_user_name: Optional[str] = None) -> tuple[str, int]:
        """Download the web page, and extract the max rank"""
        rank = "Copper"
        # Step 1: Check if the Ubisoft username is provided, otherwise use the default profile
        if ubisoft_user_name is None:
            ubisoft_user_name = self.default_profile

        try:
            # Step 2: Download the page content
            self.counter += 1
            if not ubisoft_user_name:
                print_error_log("download_max_rank: Ubisoft username not found.")
                return rank
            api_url = get_url_api_user_info(ubisoft_user_name)
            self.driver.get(api_url)
            print_log(f"download_max_rank: Downloading profile for {ubisoft_user_name} using {api_url}")
            # Wait until the page contains the expected JSON data
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "pre")))

            # Step 3: Extract the page content, expecting JSON
            page_source = self.driver.page_source

            # Step 4: Remove the HTML
            soup = BeautifulSoup(page_source, "html.parser")
            # Find the <pre> tag containing the JSON
            pre_tag = soup.find("pre")

            # Ensure the <pre> tag is found and contains the expected JSON data
            if pre_tag:
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
                    data_json = parse_json_max_rank(
                        data,
                    )
                    return data_json
                except json.JSONDecodeError as e:
                    print_error_log(f"download_max_rank: Error parsing JSON: {e}")
            else:
                print_error_log("download_max_rank: JSON data not found within <pre> tag.")
            return rank

        except Exception as e:
            print_error_log(f"download_max_rank: Error executing JavaScript to extract rank: {e}")

        if rank in siege_ranks:
            return rank
        else:
            print_error_log(f"download_max_rank: Rank {rank} not found in the list of ranks. Gave Copper instead.")
            return "Copper"

    def download_full_user_information(self, user_queued: UserQueueForStats) -> Union[UserInformation, None]:
        """
        Download the user stats for the given Ubisoft username
        """
        # # Step 1: Download the page content
        self.counter += 1
        ubisoft_user_name = user_queued.user_info.ubisoft_username_active
        if not ubisoft_user_name:
            print_error_log("download_full_user_stats: Ubisoft username not found.")
            return None
        api_url = get_url_api_user_info(ubisoft_user_name)
        self.driver.get(api_url)
        print_log(f"download_full_user_stats: Downloading stats for {ubisoft_user_name} using {api_url}")
        # Wait until the page contains the expected JSON data
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "pre")))

        # Step 2: Extract the page content, expecting JSON
        page_source = self.driver.page_source

        # Step 3: Remove the HTML
        soup = BeautifulSoup(page_source, "html.parser")
        # Find the <pre> tag containing the JSON
        pre_tag = soup.find("pre")

        # Ensure the <pre> tag is found and contains the expected JSON data
        if pre_tag:
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
                print_error_log(f"download_full_user_stats: Error parsing JSON: {e}")
        else:
            print_error_log("download_full_user_stats: JSON data not found within <pre> tag.")
        return None
