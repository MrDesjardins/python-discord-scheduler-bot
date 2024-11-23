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
from deps.models import UserMatchInfo
from deps.log import print_error_log, print_log
from deps.functions_r6_tracker import parse_json_from_matches


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
            profile_url = "https://r6.tracker.network/r6siege/profile/ubi/nosleep_rb6/matches?playlist=pvp_ranked"
            self.driver.get(profile_url)
            WebDriverWait(self.driver, 15).until(EC.visibility_of_element_located((By.ID, "app-container")))
        except Exception as e:
            print_error_log(f"_config_browser: Error visiting the profile page: {e}")

    def download_matches(self, ubisoft_user_name: str) -> List[UserMatchInfo]:
        """Download the matches for the given Ubisoft username"""
        # # Step 1: Download the page content
        self.counter += 1
        api_url = f"https://api.tracker.gg/api/v2/r6siege/standard/matches/ubi/{ubisoft_user_name}?gamemode=pvp_ranked"
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
