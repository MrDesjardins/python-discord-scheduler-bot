""" R6 Tracker API functions """

import os
from typing import List, Optional
import json
from datetime import datetime
from dateutil import parser
import requests
from bs4 import BeautifulSoup
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats, UserMatchInfoSessionAggregate
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


def parse_json_from_full_matches(data_dict, user_info: UserInfo) -> List[UserFullMatchStats]:
    """
    Function to parse the JSON dictionary into dataclasses
    The parse function returns more information than the one for the summary.
    """
    try:
        matches = data_dict["data"]["matches"]
        if not isinstance(matches, list) or len(matches) == 0:
            return []
    except KeyError as e:
        print_error_log(
            f"parse_json_from_full_matches: KeyError: {e} not found in the JSON data when parsing for active user: {user_info.ubisoft_username_active}."
        )
        return []
    except TypeError as e:
        print_error_log(f"parse_json_from_full_matches: TypeError: Unexpected data format - {e}")
        return []
    # Loopp all matches
    match_infos = []
    for match in matches:
        try:
            match_metadata = match["metadata"]
            segments = match.get("segments", [])
            if not segments:
                print("Warning: Empty segments in match data.")
                continue  # Skip if segments are empty
            segment = segments[0]
            metadata = segment["metadata"]
            stats = segment["stats"]

            match_infos.append(
                UserFullMatchStats(
                    user_id=user_info.id,
                    match_uuid=match.get("attributes", {}).get("id", "Unknown"),
                    match_timestamp=parser.parse(match_metadata.get("timestamp", "1970-01-01T00:00:00Z")),
                    match_duration_ms=match_metadata.get("duration", 0) or 0,
                    data_center=match_metadata.get("datacenter", "Unknown"),
                    session_type=match_metadata.get("sessionTypeName", "Unknown"),
                    map_name=match_metadata.get("sessionMapName", "Unknown"),
                    is_surrender=match_metadata.get("isSurrender", False) or False,
                    is_forfeit=match_metadata.get("isForfeit", False) or False,
                    is_rollback=match_metadata.get("isRollback", False) or False,
                    r6_tracker_user_uuid=segment.get("attributes", {}).get("playerId", "Unknown"),
                    ubisoft_username=metadata.get("platformUserHandle", user_info.ubisoft_username_active),
                    operators=",".join(operator.get("name", "Unknown") for operator in metadata.get("operators", [])),
                    round_played_count=stats.get("roundsPlayed", {}).get("value", 0) or 0,
                    round_won_count=stats.get("roundsWon", {}).get("value", 0) or 0,
                    round_lost_count=stats.get("roundsLost", {}).get("value", 0) or 0,
                    round_disconnected_count=stats.get("roundsDisconnected", {}).get("value", 0) or 0,
                    kill_count=stats.get("kills", {}).get("value", 0) or 0,
                    death_count=stats.get("deaths", {}).get("value", 0) or 0,
                    assist_count=stats.get("assists", {}).get("value", 0) or 0,
                    head_shot_count=stats.get("headshots", {}).get("value", 0) or 0,
                    tk_count=stats.get("teamKills", {}).get("value", 0) or 0,
                    ace_count=stats.get("aces", {}).get("value", 0) or 0,
                    first_kill_count=stats.get("firstBloods", {}).get("value", 0) or 0,
                    first_death_count=stats.get("firstDeaths", {}).get("value", 0) or 0,
                    clutches_win_count=stats.get("clutches", {}).get("value", 0) or 0,
                    clutches_loss_count=stats.get("clutchesLost", {}).get("value", 0) or 0,
                    clutches_win_count_1v1=stats.get("clutches1v1", {}).get("value", 0) or 0,
                    clutches_win_count_1v2=stats.get("clutches1v2", {}).get("value", 0) or 0,
                    clutches_win_count_1v3=stats.get("clutches1v3", {}).get("value", 0) or 0,
                    clutches_win_count_1v4=stats.get("clutches1v4", {}).get("value", 0) or 0,
                    clutches_win_count_1v5=stats.get("clutches1v5", {}).get("value", 0) or 0,
                    clutches_lost_count_1v1=stats.get("clutchesLost1v1", {}).get("value", 0) or 0,
                    clutches_lost_count_1v2=stats.get("clutchesLost1v2", {}).get("value", 0) or 0,
                    clutches_lost_count_1v3=stats.get("clutchesLost1v3", {}).get("value", 0) or 0,
                    clutches_lost_count_1v4=stats.get("clutchesLost1v4", {}).get("value", 0) or 0,
                    clutches_lost_count_1v5=stats.get("clutchesLost1v5", {}).get("value", 0) or 0,
                    kill_1_count=stats.get("kills1K", {}).get("value", 0) or 0,
                    kill_2_count=stats.get("kills2K", {}).get("value", 0) or 0,
                    kill_3_count=stats.get("kills3K", {}).get("value", 0) or 0,
                    kill_4_count=stats.get("kills4K", {}).get("value", 0) or 0,
                    kill_5_count=stats.get("kills5K", {}).get("value", 0) or 0,
                    rank_points=stats.get("rankPoints", {}).get("value", 0) or 0,
                    rank_name=stats.get("rankPoints", {}).get("metadata", {}).get("name", "Unknown"),
                    points_gained=stats.get("rankPointsDelta", {}).get("value", 0) or 0,
                    rank_previous=stats.get("rankPointsPrevious", {}).get("value", 0) or 0,
                    kd_ratio=stats.get("kdRatio", {}).get("value", 0) or 0,
                    head_shot_percentage=stats.get("headshotPct", {}).get("value", 0) or 0,
                    kills_per_round=stats.get("killsPerRound", {}).get("value", 0) or 0,
                    deaths_per_round=stats.get("deathsPerRound", {}).get("value", 0) or 0,
                    assists_per_round=stats.get("assistsPerRound", {}).get("value", 0) or 0,
                    has_win=stats.get("wins", {}).get("value", 0) == 1,
                )
            )
        except (KeyError, IndexError, TypeError) as e:
            print_error_log(f"parse_json_from_full_matches: Error processing match data: {e}")
            continue
    return match_infos


def get_user_gaming_session_stats(
    username: str, from_datetime: datetime, list_matches: List[UserFullMatchStats]
) -> Optional[UserMatchInfoSessionAggregate]:
    """
    Get the aggregate of the user's gaming session. A gaming session is from the time we pass. It should be the last ~24h.
    """
    # Get the matches after the from_datetime
    matches_recent = [
        match for match in list_matches if match.match_timestamp > from_datetime and match.is_rollback is False
    ]
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
