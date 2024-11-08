""" R6 Tracker API functions """

import os
from datetime import datetime
from typing import List, Optional
import json
import requests
import cloudscraper
import undetected_chromedriver as uc
import time
from bs4 import BeautifulSoup
from deps.models import UserMatchInfo, UserMatchInfoSessionAggregate
from deps.siege import siege_ranks
from deps.log import print_error_log
import random


TRN_API_KEY = os.getenv("TRN_API_KEY")


async def get_r6tracker_max_rank(ubisoft_user_name: str) -> str:
    """Download the web page, and extract the max rank"""
    rank = "Copper"
    url = f"https://r6.tracker.network/r6siege/profile/ubi/{ubisoft_user_name}/overview"
    # Download the web page
    try:
        page = requests.get(url, timeout=5)
        page.raise_for_status()  # Check if the request was successful
    except requests.exceptions.RequestException:
        return rank

    # Parse the page content
    soup = BeautifulSoup(page.content, "html.parser")
    element = soup.find(class_="season-peaks__seasons")
    if element:
        # Find the first <img> within this element
        img_tag = element.find("img")

        if img_tag:
            alt_name_image = img_tag.get("alt")
            rank = alt_name_image.split(" ")[0].lower().capitalize()

    if rank in siege_ranks:
        return rank
    else:
        return "Copper"


# curl ^"https://api.tracker.gg/api/v2/r6siege/standard/matches/ubi/noSleep_rb6?gamemode=pvp_ranked^" ^
#   -H ^"accept: application/json, text/plain, */*^" ^
#   -H ^"accept-language: en-US,en;q=0.9,fr-CA;q=0.8,fr;q=0.7^" ^
#   -H ^"cookie: X-Mapping-Server=s13; __cflb=02DiuFQAkRrzD1P1mdkJhfdTc9AmTWwYk4f6Y22nmXCKN; __cf_bm=Oukhd0sMUTvpa7HmjSrMAv.1fEyrpXSD4ZJnBn4xV10-1731018364-1.0.1.1-X9q64JztZ3Df5.Tk7qA6rDTIi.OIzip8e8TKRnkbeOVhgC3JWkzDCTf49nOkuyia7TJr_VSIxxAmn5T9_n7Y4PByoK94AjTmpTwTz5fNWRk^" ^
#   -H ^"if-modified-since: Thu, 07 Nov 2024 22:26:05 GMT^" ^
#   -H ^"origin: https://r6.tracker.network^" ^
#   -H ^"priority: u=1, i^" ^
#   -H ^"referer: https://r6.tracker.network/^" ^
#   -H ^"sec-ch-ua: ^\^"Chromium^\^";v=^\^"130^\^", ^\^"Google Chrome^\^";v=^\^"130^\^", ^\^"Not?A_Brand^\^";v=^\^"99^\^"^" ^
#   -H ^"sec-ch-ua-mobile: ?0^" ^
#   -H ^"sec-ch-ua-platform: ^\^"Windows^\^"^" ^
#   -H ^"sec-fetch-dest: empty^" ^
#   -H ^"sec-fetch-mode: cors^" ^
#   -H ^"sec-fetch-site: cross-site^" ^
#   -H ^"user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36^"


def download_using_chrome_driver() -> Optional[any]:
    """
    Slow approach but works to not get the 403 error or blocked request
    It goes first to the website to get the proper cookies and then to the API
    Must not be headless to work
    """
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")
    options.binary_location = "/usr/bin/google-chrome"  # Adjust this if needed for WSL

    driver = uc.Chrome(options=options)
    # Step 2: Visit the public profile page to establish the session
    profile_url = "https://r6.tracker.network/r6siege/profile/ubi/noSleep_rb6/matches?playlist=pvp_ranked"
    driver.get(profile_url)
    time.sleep(5)  # Give some time for all cookies and scripts to load

    # Step 3: Check cookies (optional, for debugging)
    cookies = driver.get_cookies()

    # Step 4: Now, navigate to the API endpoint
    api_url = "https://api.tracker.gg/api/v2/r6siege/standard/matches/ubi/nosleep_rb6?gamemode=pvp_ranked"
    driver.get(api_url)
    time.sleep(3)  # Let the request complete

    # Step 5: Extract the page content, expecting JSON
    page_source = driver.page_source
    driver.quit()

    # Step 6: Remove the HTML
    soup = BeautifulSoup(page_source, "html.parser")
    # Find the <pre> tag containing the JSON
    pre_tag = soup.find("pre")

    # Ensure the <pre> tag is found and contains the expected JSON data
    if pre_tag:
        # Extract the text content of the <pre> tag
        json_data = pre_tag.get_text().strip()

        try:
            # Parse the JSON data
            data = json.loads(json_data)

            return data
        except json.JSONDecodeError as e:
            print_error_log(f"download_using_chrome_driver: Error parsing JSON: {e}")
    else:
        print_error_log("download_using_chrome_driver: JSON data not found within <pre> tag.")
    return None


def download_using_cloudscraper() -> Optional[str]:
    """
    Download the data using cloudscraper to bypass the Cloudflare protection
    """
    scraper = cloudscraper.create_scraper()
    url = "https://api.tracker.gg/api/v2/r6siege/standard/matches/ubi/nosleep_rb6?gamemode=pvp_ranked"
    response = scraper.get(url)

    # Check if the response is JSON
    try:
        content = response.json()
        return content
    except ValueError:
        content = response.text
        print_error_log(f"download_using_cloudscraper: Unexpected response content: {content}")
        return None


def download_stub_file() -> Optional[str]:
    """ 
    Temporary until we get the API KEY
    """
    with open("./tests/tests_assets/player_rank_history.json", "r", encoding="utf8") as file:
        data = json.loads(file.read())
        return data


def get_r6tracker_user_recent_matches(ubisoft_user_name: str) -> List[UserMatchInfo]:
    """Download the web page, and extract the matches data"""

    # Set up undetected Chrome driver with enhanced options
    matches_dict = download_using_chrome_driver()
    match_obj_list = parse_json_from_matches(matches_dict, ubisoft_user_name)
    return match_obj_list


def parse_json_from_matches(data_dict, user_ubisoft_name: str) -> List[UserMatchInfo]:
    """Function to parse the JSON dictionary into dataclasses"""
    try:
        matches = data_dict["data"]["matches"]
        if not isinstance(matches, list) or len(matches) == 0:
            return []
    except KeyError as e:
        print_error_log(f"parse_json_from_matches: KeyError: {e} not found in the JSON data.")
        return []
    except TypeError as e:
        print_error_log(f"parse_json_from_matches: TypeError: Unexpected data format - {e}")
        return []
    # Loopp all matches
    match_infos = []
    for match in matches:
        try:
            segments = match.get("segments", [])
            if not segments:
                print("Warning: Empty segments in match data.")
                continue  # Skip if segments are empty
            segment = segments[0]
            stats = segment["stats"]
            match_infos.append(
                UserMatchInfo(
                    match_uuid=match["attributes"]["id"],
                    r6_tracker_user_uuid=segment["attributes"]["playerId"],
                    user_ubisoft_name=user_ubisoft_name,
                    match_timestamp=datetime.fromisoformat(match["metadata"]["timestamp"]),
                    match_duration_ms=match["metadata"]["duration"],
                    map_name=match["metadata"]["sessionMapName"],
                    has_win=stats["wins"]["value"] == 1,
                    has_ace=stats["aces"]["value"] > 0,
                    assist_count=stats["assists"]["value"],
                    death_count=stats["deaths"]["value"],
                    kd_ratio=stats["kdRatio"]["value"],
                    kill_count=stats["kills"]["value"],
                    tk_count=stats["teamKills"]["value"],
                    rank_points=stats["rankPoints"]["value"],
                    points_gained=stats["rankPointsDelta"]["value"],
                    round_count=stats["roundsPlayed"]["value"],
                    round_win_count=stats["roundsWon"]["value"],
                )
            )
        except (KeyError, IndexError, TypeError) as e:
            print_error_log(f"parse_json_from_matches: Error processing match data: {e}")
            continue
    return match_infos


def get_user_gaming_session_stats(
    username: str, from_datetime: datetime, list_matches: List[UserMatchInfo]
) -> Optional[UserMatchInfoSessionAggregate]:
    """
    Get the aggregate of the user's gaming session. A gaming session is from the time we pass. It should be the last ~24h.
    """
    # Get the matches after the from_datetime
    matches_recent = [match for match in list_matches if match.match_timestamp > from_datetime]
    if len(matches_recent) == 0:
        return None
    return UserMatchInfoSessionAggregate(
        match_count=len(matches_recent),
        match_win_count=sum(match.has_win for match in matches_recent),
        match_loss_count=len(matches_recent) - sum(match.has_win for match in matches_recent),
        total_kill_count=sum(match.kill_count for match in matches_recent),
        total_death_count=sum(match.death_count for match in matches_recent),
        total_assist_count=sum(match.assist_count for match in matches_recent),
        total_tk_count=sum(match.tk_count for match in matches_recent),
        started_rank_points=(
            matches_recent[-1].rank_points - matches_recent[-1].points_gained if matches_recent else 0
        ),  # Subtract the points gained in the match to get the starting rank points
        ended_rank_points=matches_recent[0].rank_points if matches_recent else 0,
        total_gained_points=sum(match.points_gained for match in matches_recent),
        user_ubisoft_name=username,
        kill_death=[f"{match.kill_count}/{match.death_count}/{match.assist_count}" for match in matches_recent],
    )
