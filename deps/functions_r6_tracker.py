""" R6 Tracker API functions """

import os
from typing import List, Optional
import json
from datetime import datetime
from dateutil import parser
import requests
from bs4 import BeautifulSoup
from deps.models import UserMatchInfo, UserMatchInfoSessionAggregate
from deps.siege import siege_ranks
from deps.log import print_error_log
from deps.functions import get_url_user_profile_overview

TRN_API_KEY = os.getenv("TRN_API_KEY")


async def get_r6tracker_max_rank(ubisoft_user_name: str) -> str:
    """Download the web page, and extract the max rank"""
    rank = "Copper"
    url = get_url_user_profile_overview(ubisoft_user_name)
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


# curl ^"https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/noSleep_rb6?gamemode=pvp_ranked^" ^
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


def download_stub_file() -> Optional[str]:
    """
    Temporary until we get the API KEY
    """
    with open("./tests/tests_assets/player_rank_history.json", "r", encoding="utf8") as file:
        data = json.loads(file.read())
        return data


def parse_json_from_matches(data_dict, ubisoft_username: str) -> List[UserMatchInfo]:
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
                    ubisoft_username=ubisoft_username,
                    match_timestamp=parser.parse(match["metadata"]["timestamp"]),
                    match_duration_ms=match["metadata"]["duration"],
                    map_name=match["metadata"]["sessionMapName"],
                    has_win=stats["wins"]["value"] == 1,
                    ace_count=stats["aces"]["value"],
                    kill_3_count=stats["kills3K"]["value"],
                    kill_4_count=stats["kills4K"]["value"],
                    assist_count=stats["assists"]["value"],
                    death_count=stats["deaths"]["value"],
                    kd_ratio=stats["kdRatio"]["value"],
                    kill_count=stats["kills"]["value"],
                    tk_count=stats["teamKills"]["value"],
                    rank_points=stats["rankPoints"]["value"],
                    points_gained=stats["rankPointsDelta"]["value"],
                    round_count=stats["roundsPlayed"]["value"],
                    round_win_count=stats["roundsWon"]["value"],
                    clutches_win_count=stats["clutches"]["value"],
                    clutches_loss_count=stats["clutchesLost"]["value"],
                    first_death_count=stats["firstDeaths"]["value"],
                    first_kill_count=stats["firstBloods"]["value"],
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
        matches_recent=matches_recent,
        match_count=len(matches_recent),
        match_win_count=sum(match.has_win for match in matches_recent),
        match_loss_count=len(matches_recent) - sum(match.has_win for match in matches_recent),
        total_kill_count=sum(match.kill_count for match in matches_recent),
        total_death_count=sum(match.death_count for match in matches_recent),
        total_assist_count=sum(match.assist_count for match in matches_recent),
        total_tk_count=sum(match.tk_count for match in matches_recent),
        started_rank_points=(
            matches_recent[-1].rank_points - (matches_recent[-1].points_gained or 0) if matches_recent else 0
        ),  # Subtract the points gained in the match to get the starting rank points
        ended_rank_points=matches_recent[0].rank_points if matches_recent else 0,
        total_gained_points=sum((match.points_gained or 0) for match in matches_recent),
        ubisoft_username_active=username,
        total_round_with_aces=sum(match.ace_count for match in matches_recent),
        total_round_with_3k=sum(match.kill_3_count for match in matches_recent),
        total_round_with_4k=sum(match.kill_4_count for match in matches_recent),
        total_clutches_win_count=sum(match.clutches_win_count for match in matches_recent),
        total_clutches_loss_count=sum(match.clutches_loss_count for match in matches_recent),
        total_first_death_count=sum(match.first_death_count for match in matches_recent),
        total_first_kill_count=sum(match.first_kill_count for match in matches_recent),
    )
