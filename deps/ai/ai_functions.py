"""
Generate message for the matches played by the users
"""

from datetime import datetime, timedelta, timezone
import os
import json
from typing import List
from dotenv import load_dotenv
from google import genai
from deps.analytic_data_access import data_access_fetch_user_full_match_info, get_active_user_info
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats
from deps.log import print_error_log, print_log


load_dotenv()

ENV = os.getenv("ENV")
KEY = os.getenv("GEMINI_API_KEY")


def ask_gemini(question: str) -> str:
    """
    Ask Gemini a question and return the answer.
    """
    # Set up the API client

    client = genai.Client(api_key=KEY)
    response = client.models.generate_content(model="gemini-2.0-flash-001", contents=question)
    return response.text


def gather_information_for_generating_message_summary(hours) -> tuple[List[UserInfo], list[UserFullMatchStats]]:
    """
    Gather information for generating a message summary.
    """
    from_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    to_time = datetime.now(timezone.utc)
    users: List[UserInfo] = get_active_user_info(from_time, to_time)
    print_log(f"gather_information_for_generating_message_summary: Found {len(users)} users")
    full_matches_info_by_user_id = []
    r6_user_dict = {}
    for user in users:
        # Keep only the data for matched in the last hours
        data_from_last_hours = data_access_fetch_user_full_match_info(user.id)
        for match in data_from_last_hours:
            if from_time <= match.match_timestamp and match.match_timestamp <= to_time:
                r6_user_dict[match.r6_tracker_user_uuid] = match.r6_tracker_user_uuid
                full_matches_info_by_user_id.append(match)
    print_log(
        f"gather_information_for_generating_message_summary: full_matches_info_by_user_id {len(full_matches_info_by_user_id)} matches"
    )
    # Remove users who have not match in the full_matches_info_by_user_id (by looking at the r6_tracker_active_id)
    users = [user for user in users if r6_user_dict.get(str(user.r6_tracker_active_id)) is not None]
    print_log(f"gather_information_for_generating_message_summary: Found {len(users)} users with matches")
    return users, full_matches_info_by_user_id


def generate_message_summary_matches(hours: int) -> str:
    """
    Generate a message summary of the matches played by the users.
    """
    users, full_matches_info_by_user_id = gather_information_for_generating_message_summary(hours)
    user_info_serialized = json.dumps([u.__dict__ for u in users])  # Serialize the value
    match_info_serialized = json.dumps([m.to_dict() for m in full_matches_info_by_user_id])

    context = "Your goal is to generate a summary of maximum 6000 characters (including white space and change line) of the matches played by the users"
    context += "I am providing you a list of users and a list of their matches. You need to use both."
    context += "Your message must give one or three sentences about each user."
    context += "You need to find something to say for every one if they have at least one match. If not match, say nothing, don't even say they did not play."
    context += "Please mention every user by their display_name, so you must match the user id with the display_name."
    context += "Provide an highlight of the matches played when something interesting happened. Try to find the best match of the user and the worst match."
    context += "Try to make relationship between the users who played the same match using the r6_tracker_active_id and r6_tracker_user_uuid"
    context += "Information that are valuable are the number of clutches, ace and 1v2, 1v3, 1v4 and 1v5 especially against multiple enemies, kd ratios above 1, and number of kills above 5. The value of tk_count is interesting since they show a huge blunder. A head shot percentage above 0.5 is also interesting."
    context += "For the match summary, ensure to talk about the map and operators if something stand out and talk about the overall wins (look at has_win)."
    context += "A summary of the total points gained when interesting. Keep it short and concise."
    context += "Here is the list of the users:"
    context += user_info_serialized
    context += "Here is the list of the matches with in a dictionary format where the key is the user id:"
    context += match_info_serialized
    context += "Format in a way that does not mention the request of this message and that it is easy to split in chunk of 2000 characters."
    context += "Try to have the tone of a sport commentary."
    context += "Dont mention anything about what I asked you to do, just the result."
    context += "Dont mention any ID, for example do not talk about r6_tracker_active_id or match uuid."
    context += "Change line without empty line (do not add two new lines in a row)."
    context += "Format your text not in bullet point, but in a text like we would read in a sport news paper."
    context += "Be professional, sport and concise. Do not add any emoji or special character."
    try:
        response = f"✨**AI summary generated of the last {hours} hours**✨\n" + ask_gemini(context)
    except Exception as e:
        print_error_log(f"Error while asking Gemini: {e}")
        return ""
    return response
