"""Browser Context Manager to handle the browser and download the matches from the Ubisoft API"""

import signal
import subprocess
from filelock import FileLock
import subprocess
import shutil
import os, time
from typing import List, Optional, Union
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc  # type: ignore
from bs4 import BeautifulSoup
from deps.models import UserFullMatchStats, UserInformation, UserQueueForStats
from deps.log import print_error_log, print_log
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

    def __enter__(self):
        retries = 2
        for i in range(retries):
            try:
                self._lock.acquire(timeout=120)
                self._lock_acquired = True
                self._config_browser()
                return self
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

        # 1. Try to quit the driver gracefully
        if self.driver:
            try:
                # Get the PID before quitting
                browser_pid = self.driver.browser_pid
                self.driver.quit()
                # Force kill the specific browser PID just in case
                os.kill(browser_pid, signal.SIGKILL)
            except:
                pass
            self.driver = None

        # 2. Kill the Xvfb process group (the nuclear option)
        if self._xvfb_proc:
            try:
                # This kills the Xvfb AND any children it spawned
                os.killpg(os.getpgid(self._xvfb_proc.pid), signal.SIGKILL)
            except:
                pass
            self._xvfb_proc = None

        # 3. Final Wipe of the specific profile directory
        if self._profile_dir and os.path.exists(self._profile_dir):
            shutil.rmtree(self._profile_dir, ignore_errors=True)

        if self._lock_acquired:
            try:
                self._lock.release()
            except:
                pass
            self._lock_acquired = False

    def _config_browser(self):
        options = uc.ChromeOptions()
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
                    with open(f"r6tracker_data_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
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
                        with open(f"r6tracker_data_{self.counter}.json", "w", encoding="utf8") as file:
                            file.write(json.dumps(data, indent=4))
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
                    with open(f"r6tracker_data_full_user_stats_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
                # Step 6: Parse the JSON data to extract the matches
                return parse_json_user_info(user_queued.user_info.id, data)
            except json.JSONDecodeError as e:
                print_error_log(f"download_full_user_stats: Error parsing JSON: {e}")
        else:
            print_error_log("download_full_user_stats: JSON data not found within <pre> tag.")
        return None
