""" R6 Tracker API functions """

from datetime import datetime
from typing import List, Optional
import json
import requests
from bs4 import BeautifulSoup
from deps.models import UserMatchInfo, UserMatchInfoSessionAggregate
from deps.siege import siege_ranks


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


def get_r6tracker_user_recent_matches(ubisoft_user_name: str) -> List[UserMatchInfo]:
    """Download the web page, and extract the matches data"""
    url = f"https://api.tracker.gg/api/v2/r6siege/standard/matches/ubi/${ubisoft_user_name}?gamemode=pvp_ranked"
    # Download the web page
    try:
        page = requests.get(url, timeout=5)
        content = page.content()  # Check if the request was successful
        page.raise_for_status()  # Check if the request was successful
    except requests.exceptions.RequestException:
        return None

    # Parse the page content
    matches_dict = json.loads(content)
    match_obj_list = parse_json_from_matches(matches_dict, ubisoft_user_name)
    return match_obj_list

def parse_json_from_matches(data_dict, user_ubisoft_name: str) -> List[UserMatchInfo]:
    """ Function to parse the JSON dictionary into dataclasses"""
    try:
        matches = data_dict["data"]["matches"]
        if not isinstance(matches, list) or len(matches) == 0:
            return []
    except KeyError as e:
        print(f"KeyError: {e} not found in the JSON data.")
        return []
    except TypeError as e:
        print(f"TypeError: Unexpected data format - {e}")
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
            print(f"Error processing match data: {e}")
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
