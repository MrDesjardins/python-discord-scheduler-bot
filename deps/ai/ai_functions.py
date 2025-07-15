"""
Generate message for the matches played by the users
"""

from datetime import datetime, timedelta, timezone
import os
import json
import asyncio
from typing import List, Union
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
    Ask Gemini a question and return the answer (blocking).
    """
    client = genai.Client(api_key=KEY)
    response = client.models.generate_content(model="gemini-2.5-flash", contents=question)
    return response.text


async def ask_gemini_async(question: str, timeout: float = 300.0) -> Union[str, None]:
    """
    Ask Gemini a question and return the answer (non-blocking, async, with timeout).
    """
    try:
        return await asyncio.wait_for(asyncio.to_thread(ask_gemini, question), timeout=timeout)
    except asyncio.TimeoutError:
        print_error_log(f"Gemini API call timed out after {timeout} seconds.")
        return None


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


async def generate_message_summary_matches_async(hours: int) -> str:
    """
    Async version: Generate a message summary of the matches played by the users without blocking the event loop.
    """
    users, full_matches_info_by_user_id = gather_information_for_generating_message_summary(hours)
    user_info_serialized = json.dumps([u.__dict__ for u in users])
    match_info_serialized = "\n".join([summarize_full_match(m) for m in full_matches_info_by_user_id])
    context = "Your goal is to generate a summary of maximum 6000 characters (including white space and change line) of the matches played by the users."
    context += "I am providing you a list of users and a list of their matches. You can use the match id and user id to make some relationship with the user and the match. You need to use both."
    context += "Your message must never have more than 100 words per user."
    context += "You need to find something to say for every one if they have at least one match. If not match, say nothing, don't even say they did not play."
    context += "Please mention every user by their display_name, so you must match the user id with the display_name."
    context += "Provide an highlight of the matches played when something interesting happened. Try to find the best match of the user and the worst match."
    context += "Try to make relationship between the users who played the same match using the r6_tracker_active_id and r6_tracker_user_uuid"
    context += "Information that are valuable are the number of clutches, ace and 1v2, 1v3, 1v4 and 1v5 especially against multiple enemies, kd ratios above 1, and number of kills above 5. "
    context += "The value of team kills is interesting since they show a huge blunder. A head shot percentage above 0.5 is also interesting."
    context += "A number of kills above 8 is good, above 12 is very good, above 15 is exceptional."
    context += "For the match summary, ensure to talk about the map and operators if something stand out and talk about the overall wins within all the stats for each user."
    context += "If a user won more than half of the matches, mention it because it is very good."
    context += "A summary of the total points gained when interesting. Keep it short and concise."
    context += "Here is the list of the users:"
    context += user_info_serialized
    context += "Here is the list of the matches summarized:"
    context += match_info_serialized
    context += "Format in a way that does not mention the request of this message and that it is easy to split in chunk of 2000 characters."
    context += "Try to have the tone of a sport commentary."
    context += "Dont mention anything about what I asked you to do, just the result."
    context += "Dont mention any ID, for example do not talk about r6_tracker_active_id or match uuid."
    context += "Dont mention any thing about the time. I provide the time and match id for your to correlate the users and matches."
    context += "Change line without empty line (do not add two new lines in a row)."
    context += "Format your text not in bullet point, but in a text like we would read in a sport news paper."
    context += "Be professional, sport and concise. Do not add any emoji or special character."
    context += "If the display_name is 'Obey' prefix with the name with 'ultimate champion'"
    context += "If the display_name is 'Dom1nator.gov' prefix the name with 'legendary'"
    try:
        print_log(
            f"generate_message_summary_matches_async: Asking Gemini for {hours} hours summary that contained a size of {len(context)} characters. The data contains {len(users)} users and {len(full_matches_info_by_user_id)} matches."
        )
        gemini_response = await ask_gemini_async(context)
        if gemini_response is None:
            print_error_log("Error: Gemini response is None.")
            with open("gemini_context.txt", "w", encoding="utf-8") as f:
                f.write(context)
            print_error_log("Context dumped in gemini_context.txt")
            return ""
        response = f"✨**AI summary generated of the last {hours} hours**✨\n" + gemini_response
    except Exception as e:
        print_error_log(f"Error while asking Gemini: {e}")
        return ""
    return response


async def generate_answer_when_mentioning_bot(
    context_previous_messages: str, message_user: str, user_display_name: str
) -> str:
    """
    Generate an answer when the bot is mentioned.
    """
    context = "You are a bot that is mentioned in a Discord server. You need to answer to the user who mentioned you."
    context += "You should not mention anything about your name or your purpose, just answer the question."
    context += "Here is the context of some previous message that might help you crafting the best response:"
    context += "Previous messages: " + context_previous_messages
    context += "User question:" + message_user
    u = user_display_name.lower()
    if "obey" in u or "funky" in u:
        context += "The user is called Obey but in your message call him 'champion'."
        context += "The user like sarcasm, so answer in a sarcastic tone."
    else:
        context += "You are a bot that is friendly, helpful and professional. You should not be rude or sarcastic."
        context += "You should answer in a way that is easy to read and understand under 800 characters."
    try:
        response = await ask_gemini_async(context)
    except Exception as e:
        print_error_log(f"Error while asking Gemini: {e}")
        return ""
    return response


def summarize_full_match(match: UserFullMatchStats) -> str:
    """
    Summarize a full match in a string format.
    """
    summary = f"""
This the match information for match id {match.match_uuid} played on {match.match_timestamp.strftime('%Y-%m-%d %H:%M:%S')} for user id {match.user_id} who also share this r6_tracker_active_id: {match.r6_tracker_user_uuid}.
The user played on the map {match.map_name} with the following operators: {match.operators}.
The match had {match.round_played_count} rounds. {match.round_won_count} rounds were won by the user and {match.round_lost_count} rounds were lost. 
The final result was a {"win" if match.has_win else "loss"}.
{"The match was a rollback." if match.is_rollback else ""}
{"The match was surrendered." if match.is_surrender else ""}
A k/d (kill/death ratio) of {match.kd_ratio} with {match.kill_count} kills and {match.death_count} deaths with {match.assist_count} assists.
Had {match.head_shot_count} head shots.
{"Disconnected" + f" {match.round_disconnected_count} times." if match.round_disconnected_count > 0 else ""}
{match.head_shot_count} head shots with a head shot percentage of {match.head_shot_percentage}.
{"Team killed {match.tk_count} times." if match.tk_count > 0 else ""}
{f"{match.ace_count} aces." if match.ace_count > 0 else ""}
{"Killed the opponent first " + f"{match.first_kill_count} times." if match.first_kill_count > 0 else ""}
{"Died " + f"{match.first_death_count} first." if match.first_death_count > 0 else ""}
{"Had won " + f"{match.clutches_win_count} clutch rounds." if match.clutches_win_count > 0 else ""}
{"Had lost " + f"{match.clutches_loss_count} clutch rounds." if match.clutches_loss_count > 0 else ""}
{"Won a 1v1 clutch " + f"{match.clutches_win_count_1v1} times." if match.clutches_win_count_1v1 > 0 else ""}
{"Won a 1v2 clutch " + f"{match.clutches_win_count_1v2} times" if match.clutches_win_count_1v2 > 0 else ""}
{"Won a 1v3 clutch " + f"{match.clutches_win_count_1v3} times" if match.clutches_win_count_1v3 > 0 else ""}
{"Won a 1v4 clutch " + f"{match.clutches_win_count_1v4} times." if match.clutches_win_count_1v4 > 0 else ""}
{"Won a 1v5 clutch " + f"{match.clutches_win_count_1v5} times." if match.clutches_win_count_1v5 > 0 else ""}
{"Lost a 1v1 clutch " + f"{match.clutches_lost_count_1v1} times." if match.clutches_lost_count_1v1 > 0 else ""}
{"Lost a 1v2 clutch " + f"{match.clutches_lost_count_1v2} times." if match.clutches_lost_count_1v2 > 0 else ""}
{"Lost a 1v3 clutch " + f"{match.clutches_lost_count_1v3} times." if match.clutches_lost_count_1v3 > 0 else ""}
{"Lost a 1v4 clutch " + f"{match.clutches_lost_count_1v4} times." if match.clutches_lost_count_1v4 > 0 else ""}
{"Lost a 1v5 clutch " + f"{match.clutches_lost_count_1v5} times." if match.clutches_lost_count_1v5 > 0 else ""}
The user won {match.points_gained} point rank points for a final {match.rank_points} setting the user to the rank of {match.rank_name}.
The user had a kill per round of {match.kills_per_round:.2f}, a death per round of {match.deaths_per_round:.2f} and an assist per round of {match.assists_per_round:.2f}.
End for the match id {match.match_uuid}.
"""
    # Remove the empty lines produced by the conditional string
    lines = summary.splitlines()
    non_empty_lines = [line for line in lines if line.strip()]
    cleaned_text = "\n".join(non_empty_lines)
    return cleaned_text
