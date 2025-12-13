"""Browser Context Manager to handle the browser and download the matches from the Ubisoft API"""

import os
from typing import List, Optional, Union
import json
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc  # type: ignore
from xvfbwrapper import Xvfb  # type: ignore
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


class BrowserContextManager:
    """
    Context manager to handle the browser
    Slow approach but works to not get the 403 error or blocked request
    It goes first to the website to get the proper cookies and then to the API
    Must not be headless to work

    Pre-requisite:
    sudo apt install -y xvfb
    sudo apt install chromium-browser
    """

    driver: uc.Chrome
    wrapped: Xvfb
    default_profile: str
    counter: int
    environment: Union[str, None]

    def __init__(self, default_profile: str = "noSleep_rb6") -> None:
        self.environment = os.getenv("ENV")
        #self.wrapped = None
        self.counter = 0
        self.profile_page_source = ""
        self.default_profile = default_profile

    def __enter__(self):
        self.wrapped = Xvfb()
        self.wrapped.__enter__()
        self._config_browser()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.driver.quit()
        # Kill any lingering chromium-browser processes
        if self.environment == "prod":
            os.system("pkill -f chromium-browser")
        return self.wrapped.__exit__(exc_type, exc_value, traceback)

    def _config_browser(self) -> None:
        """Configure the browser for headers and to receive a cookie to call future API endpoints"""
        options = uc.ChromeOptions()
        # options.add_argument("--headless=new")  # For Chromium versions 109+
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-sync")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36"
        )
        options.binary_location = "/usr/bin/google-chrome"
        self.driver = uc.Chrome(options=options)

        print_log(f"_config_browser: Using binary location: {options.binary_location}")
        try:
            # Step 2: Visit the public profile page to establish the session
            profile_url = get_url_user_ranked_matches(self.default_profile)
            self.driver.get(profile_url)
            WebDriverWait(self.driver, 45).until(EC.visibility_of_element_located((By.ID, "app-container")))
        except Exception as e:
            print_error_log(f"_config_browser: Error visiting the profile page ({profile_url}): {e}")
            # Throw the exception to __exit__
            raise e

    def download_full_matches(self, user_queued: UserQueueForStats) -> List[UserFullMatchStats]:
        """
        Download the matches for the given Ubisoft username
        This is version 2 of download_matches. It contains a lost more fields.
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
