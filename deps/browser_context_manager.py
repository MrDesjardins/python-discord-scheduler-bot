""" Browser Context Manager to handle the browser and download the matches from the Ubisoft API """

import os
from typing import List
import json

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from xvfbwrapper import Xvfb
from bs4 import BeautifulSoup
from deps.data_access_data_class import UserInfo
from deps.models import UserMatchInfo
from deps.log import print_error_log, print_log
from deps.functions_r6_tracker import parse_json_from_full_matches, parse_json_from_matches
from deps.functions import get_url_api_ranked_matches, get_url_user_ranked_matches


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

    def __init__(self):
        self.wrapped = None
        self.driver = None
        self.counter = 0

    def __enter__(self):
        self.wrapped = Xvfb()
        self.wrapped.__enter__()
        self._config_browser()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.driver.quit()
        # Kill any lingering chromium-browser processes
        environment_var = os.getenv("ENV")
        if environment_var == "prod":
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
        options.add_argument("--disable-sync")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36"
        )

        environment_var = os.getenv("ENV")

        if environment_var == "prod":
            options.binary_location = "/usr/bin/chromium-browser"
            driver_path = "/usr/bin/chromedriver"
            self.driver = uc.Chrome(options=options, driver_executable_path=driver_path)
        else:
            service = Service()
            options.binary_location = "/usr/bin/google-chrome"
            options = webdriver.ChromeOptions()
            self.driver = webdriver.Chrome(service=service, options=options)
        print_log(f"_config_browser: Using binary location: {options.binary_location}")
        try:
            # Step 2: Visit the public profile page to establish the session
            profile_url = get_url_user_ranked_matches("noSleep_rb6")
            self.driver.get(profile_url)
            WebDriverWait(self.driver, 45).until(EC.visibility_of_element_located((By.ID, "app-container")))
        except Exception as e:
            print_error_log(f"_config_browser: Error visiting the profile page ({profile_url}): {e}")
            # Throw the exception to __exit__
            raise e

    def download_matches(self, ubisoft_user_name: str) -> List[UserMatchInfo]:
        """Download the matches for the given Ubisoft username"""
        # # Step 1: Download the page content
        self.counter += 1
        api_url = get_url_api_ranked_matches(ubisoft_user_name)
        self.driver.get(api_url)
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
                print_log(f"download_matches: JSON data successfully parsed for {ubisoft_user_name}")
                # Save the JSON data to a file for debugging
                if os.getenv("ENV") == "dev":
                    with open(f"r6tracker_data_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
                # Step 6: Parse the JSON data to extract the matches
                return parse_json_from_matches(data, ubisoft_user_name)
            except json.JSONDecodeError as e:
                print_error_log(f"download_matches: Error parsing JSON: {e}")
        else:
            print_error_log("download_matches: JSON data not found within <pre> tag.")

    def download_full_matches(self, user_info: UserInfo) -> List[UserMatchInfo]:
        """
        Download the matches for the given Ubisoft username
        This is version 2 of download_matches. It contains a lost more fields.
        The future goal is to replace download_matches with this function.
        """
        # # Step 1: Download the page content
        self.counter += 1
        ubisoft_user_name = user_info.ubisoft_username_active
        api_url = get_url_api_ranked_matches(ubisoft_user_name)
        self.driver.get(api_url)
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
                print_log(f"download_matches: JSON data successfully parsed for {ubisoft_user_name}")
                # Save the JSON data to a file for debugging
                if os.getenv("ENV") == "dev":
                    with open(f"r6tracker_data_{self.counter}.json", "w", encoding="utf8") as file:
                        file.write(json.dumps(data, indent=4))
                # Step 6: Parse the JSON data to extract the matches
                return parse_json_from_full_matches(data, user_info)
            except json.JSONDecodeError as e:
                print_error_log(f"download_matches: Error parsing JSON: {e}")
        else:
            print_error_log("download_matches: JSON data not found within <pre> tag.")

    def refresh_browser(self) -> None:
        """Refresh the browser"""
        self.driver.refresh()
        WebDriverWait(self.driver, 15).until(EC.visibility_of_element_located((By.ID, "app-container")))
        print_log("refresh_browser: Browser refreshed")
