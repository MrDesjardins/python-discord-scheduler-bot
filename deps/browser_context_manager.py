"""Browser Context Manager to handle the browser and download the matches from the Ubisoft API"""
import signal 
import socket
import subprocess
from filelock import FileLock
import subprocess
import uuid
import shutil
import os, threading, multiprocessing, time
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
XVFB_DISPLAY = ":99"

def wait_for_port(port, host='127.0.0.1', timeout=10.0):
    """Wait until a port starts accepting TCP connections."""
    start_time = time.time()
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, socket.timeout):
            if time.time() - start_time > timeout:
                return False
            time.sleep(0.5)
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
                self._start_xvfb()
                self._config_browser()
                return self
            except Exception as e:
                print_error_log(f"Startup attempt {i+1} failed: {e}")
                self._cleanup() # Full wipe before retry
                if i == retries - 1:
                    raise
                time.sleep(2) # Breath before retry

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()
            
    def _start_xvfb(self) -> None:
            if "DISPLAY" in os.environ and not self._xvfb_proc:
                return

            display_num = 99
            # Loop to find an available display
            while display_num < 150:
                if not os.path.exists(f"/tmp/.X{display_num}-lock") and \
                not os.path.exists(f"/tmp/.X11-unix/X{display_num}"):
                    break
                display_num += 1
            
            target_display = f":{display_num}"
            print_log(f"Attempting to start Xvfb on {target_display}...")

            self._xvfb_proc = subprocess.Popen(
                ["Xvfb", target_display, "-ac", "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Export to the environment so Chrome can see it
            os.environ["DISPLAY"] = target_display
            
            # CRITICAL: Wait for the X11 socket file to actually exist
            # This prevents the "Missing X server or $DISPLAY" error
            socket_path = f"/tmp/.X11-unix/X{display_num}"
            for i in range(30): # Wait up to 3 seconds
                if os.path.exists(socket_path):
                    print_log(f"Xvfb socket found at {socket_path}. Display ready.")
                    return
                time.sleep(0.1)
            
            raise RuntimeError(f"Xvfb failed to create socket at {socket_path}")

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


    def _config_browser(self) -> None:
        options = uc.ChromeOptions()
        options.binary_location = "/usr/bin/google-chrome"
        self._profile_dir = f"/tmp/chromium-profile-{uuid.uuid4()}"
        
        # 1. CORE STABILITY
        options.add_argument(f"--user-data-dir={self._profile_dir}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        try:
            display = os.environ.get("DISPLAY")
            print_log(f"Launching Chrome ({self.environment}) on {display}")

            if self.environment == "prod":
                port = 45455
                log_path = "/tmp/chrome_debug.log"
                
                # 1. EXPLICITLY capture the environment including the new DISPLAY
                current_env = os.environ.copy()
                current_display = current_env.get("DISPLAY")
                print_log(f"Confirming DISPLAY for Chrome: {current_display}")

                chrome_cmd = [
                    "/usr/bin/google-chrome",
                    f"--remote-debugging-port={port}",
                    f"--user-data-dir={self._profile_dir}",
                    "--no-sandbox",
                    "--no-zygote",
                    "--single-process",
                    "--disable-gpu",
                    "--use-gl=swiftshader",
                    "--disable-dev-shm-usage",
                    "--disable-breakpad",
                    "--disable-software-rasterizer",
                    "--ozone-platform=x11",  # Force X11 mode for Xvfb
                    "about:blank"
                ]
                
                # 2. Pass 'env=current_env' to the Popen call
                with open(log_path, "w") as f:
                    self._chrome_msg = subprocess.Popen(
                        chrome_cmd,
                        stdout=f,
                        stderr=f,
                        env=current_env, # THIS IS CRITICAL
                        preexec_fn=os.setsid
                    )
                
                print_log(f"Waiting for Chrome to open port {port}...")
                if not wait_for_port(port, timeout=15.0):
                    with open(log_path, "r") as f:
                        errors = f.read()
                    raise RuntimeError(f"Chrome port {port} never opened! Log: {errors}")

                print_log("Port is open. Attaching driver...")
                self.driver = uc.Chrome(options=options, use_subprocess=False, port=port)
            else:
                # --- WSL (DEV) ---
                self.driver = uc.Chrome(
                    options=options,
                    headless=False,
                    use_subprocess=True,
                    port=45455
                )
            
            self.driver.set_page_load_timeout(60)
            self.driver.get(get_url_user_ranked_matches(self.default_profile))
            
            WebDriverWait(self.driver, 45).until(
                EC.visibility_of_element_located((By.ID, "app-container"))
            )
        except Exception as e:
            print_error_log(f"_config_browser: {e}")
            raise

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

    def download_max_rank(self, ubisoft_user_name: Optional[str] = None) -> str:
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
