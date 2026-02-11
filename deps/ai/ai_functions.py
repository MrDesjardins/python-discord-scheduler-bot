"""
Generate message for the matches played by the users
"""

from __future__ import annotations  # Enables forward reference resolution
from datetime import datetime, timedelta, timezone
import os
import asyncio
from typing import List, Union
from dotenv import load_dotenv
from google import genai
from openai import OpenAI
from deps.bet.bet_data_access import (
    SELECT_BET_GAME,
    SELECT_BET_USER_GAME,
    SELECT_BET_USER_TOURNAMENT,
    SELECT_LEDGER,
    KEY_bet_game,
    KEY_bet_ledger_entry,
    KEY_bet_user_game,
    KEY_bet_user_tournament,
)
from deps.data_access import (
    data_access_execute_sql_query_from_llm,
    data_access_get_ai_daily_count,
    data_access_set_ai_daily_count,
)
from deps.analytic_data_access import (
    KEY_USER_ACTIVITY,
    KEY_USER_FULL_MATCH_INFO,
    KEY_USER_FULL_STATS_INFO,
    KEY_USER_INFO,
    SELECT_USER_FULL_MATCH_INFO,
    SELECT_USER_FULL_STATS_INFO,
    USER_ACTIVITY_SELECT_FIELD,
    USER_INFO_SELECT_FIELD,
    data_access_fetch_user_full_match_info,
    data_access_fetch_user_matches_in_time_range,
    get_active_user_info,
)
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats
from deps.log import print_error_log, print_log
from deps.tournaments.tournament_data_access import (
    KEY_TOURNAMENT,
    KEY_TOURNAMENT_GAME,
    KEY_TOURNAMENT_TEAM_MEMBERS,
    KEY_USER_TOURNAMENT,
    SELECT_TOURNAMENT,
    SELECT_TOURNAMENT_GAME,
    SELECT_TOURNAMENT_TEAM_MEMBERS,
    SELECT_USER_TOURNAMENT,
)
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT
from deps.functions import escape_discord_styling

load_dotenv()

THRESHOLD_GEMINI = 250
THRESHOLD_RETRY_AI = 5


class BotAI:
    """
    Contain all the information about the bot and AI
    """

    request_counter_per_day: dict[str, int]
    is_running_ai_query: bool

    def __init__(self):
        self.request_counter_per_day = {}
        self.request_counter_per_day[self.today_key()] = 0
        self.is_running_ai_query = False

    async def load_initial_value(self):
        """
        Load from the memory cache the count
        """
        memory_count = await data_access_get_ai_daily_count()
        self.request_counter_per_day[self.today_key()] = 0 if memory_count is None else memory_count

    def is_running(self):
        """
        Indicate if a user is using the AI
        """
        return self.is_running_ai_query

    def today_key(self):
        """
        Get the current day key
        """
        today = datetime.now().date()
        today_str = today.isoformat()
        return today_str

    def increase_daily_count(self):
        """
        Keep track of the number of request
        """
        today_str = self.today_key()
        for date_str in list(self.request_counter_per_day.keys()):
            if date_str != today_str:
                del self.request_counter_per_day[date_str]
        self.request_counter_per_day[today_str] = self.request_counter_per_day.get(today_str, 0) + 1
        data_access_set_ai_daily_count(self.request_counter_per_day[today_str])

    def today_count(self):
        """
        Get the current count of AI request
        """
        today_str = self.today_key()
        return self.request_counter_per_day.get(today_str, 0)

    def ask_ai(self, question: str, use_gpt: bool = False) -> Union[str, None]:
        """
        Ask AI a question and return the answer (blocking).
        Automatically falls back from Gemini to GPT on failure.
        """
        print_log(f"ask_ai: The number of AI count today is {self.today_count()}.")

        # Determine if we should try Gemini first
        should_try_gemini = not use_gpt and self.today_count() < THRESHOLD_GEMINI

        # Try Gemini first if appropriate
        if should_try_gemini:
            try:
                gemini_key = os.getenv("GEMINI_API_KEY")
                if not gemini_key:
                    print_error_log("ask_ai: GEMINI_API_KEY not found in environment variables. Falling back to GPT.")
                else:
                    print_log("ask_ai: Attempting to use Gemini API...")
                    client_gemini = genai.Client(api_key=gemini_key)
                    response_gemini = client_gemini.models.generate_content(model="gemini-2.5-flash", contents=question)

                    if hasattr(response_gemini, "text") and response_gemini.text:
                        print_log("ask_ai: Gemini API response successful.")
                        return response_gemini.text
                    else:
                        print_error_log("ask_ai: Gemini response has no 'text' attribute or is empty. Falling back to GPT.")
            except Exception as e:
                print_error_log(f"ask_ai: Gemini API error: {e}. Falling back to GPT.")

        # Fall back to GPT (or use it if requested explicitly)
        try:
            print_log("ask_ai: Attempting to use OpenAI GPT API...")
            client_open_ai = OpenAI()
            response_open_ai = client_open_ai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": question}]
            )

            if response_open_ai.choices and len(response_open_ai.choices) > 0:
                result = response_open_ai.choices[0].message.content
                print_log("ask_ai: OpenAI GPT API response successful.")
                return result
            else:
                print_error_log("ask_ai: GPT response has no choices or is empty.")
                return None
        except Exception as e:
            print_error_log(f"ask_ai: OpenAI GPT API error: {e}")
            return None

    async def ask_ai_async(self, question: str, timeout: float = 800.0, use_gpt: bool = False) -> Union[str, None]:
        """
        Ask AI a question and return the answer (non-blocking, async, with timeout).
        Automatically falls back from Gemini to GPT on failure.
        """
        self.increase_daily_count()
        try:
            result = await asyncio.wait_for(asyncio.to_thread(self.ask_ai, question, use_gpt), timeout=timeout)
            if result is None:
                print_error_log("ask_ai_async: Both Gemini and GPT APIs failed to return a valid response.")
            return result
        except asyncio.TimeoutError:
            print_error_log(f"ask_ai_async: AI API call timed out after {timeout} seconds.")
            return None
        except Exception as e:
            print_error_log(f"ask_ai_async: Unexpected error during AI API call: {e}")
            return None

    def gather_information_for_generating_message_summary(
        self, hours
    ) -> tuple[List[UserInfo], List[UserFullMatchStats]]:
        """
        Gather information for generating a message summary.
        """
        from_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        to_time = datetime.now(timezone.utc)

        print_log(
            f"gather_information_for_generating_message_summary: "
            f"Gathering information from {from_time} to {to_time} UTC"
        )

        # Get users active in voice channels during time period
        users: List[UserInfo] = get_active_user_info(from_time, to_time)
        print_log(f"gather_information_for_generating_message_summary: Found {len(users)} active users")

        if not users:
            return [], []

        # Batch fetch all matches for all users in time range (FIXED: no pagination limit)
        user_ids = [user.id for user in users]
        matches_by_user_id = data_access_fetch_user_matches_in_time_range(
            user_ids=user_ids,
            from_timestamp=from_time,
            to_timestamp=to_time
        )

        # Flatten matches and track which users have matches
        full_matches_info_by_user_id = []
        users_with_matches = set()

        for user_id, matches in matches_by_user_id.items():
            full_matches_info_by_user_id.extend(matches)
            users_with_matches.add(user_id)

        print_log(
            f"gather_information_for_generating_message_summary: "
            f"Found {len(full_matches_info_by_user_id)} matches for {len(users_with_matches)} users"
        )

        # Filter users to only those with matches (FIXED: use user.id directly)
        users_filtered = []
        for user in users:
            if user.id in users_with_matches:
                users_filtered.append(user)
            else:
                print_log(
                    f"gather_information_for_generating_message_summary: "
                    f"User {user.display_name} (ID: {user.id}) has no matches in time range"
                )

        print_log(
            f"gather_information_for_generating_message_summary: "
            f"Returning {len(users_filtered)} users with matches"
        )

        return users_filtered, full_matches_info_by_user_id

    async def generate_message_summary_matches_async(self, hours: int) -> str:
        """
        Async version: Generate a message summary of the matches played by the users without blocking the event loop.
        Uses automatic Gemini->GPT fallback from ask_ai_async.
        """
        users, full_matches_info_by_user_id = self.gather_information_for_generating_message_summary(hours)
        if len(users) == 0 or len(full_matches_info_by_user_id) == 0:
            return f"✨**AI summary generated of the last {hours} hours**✨\nNo user played any match in the last {hours} hours."
        print_log(f"Users display name {', '.join([u.display_name for u in users])}")

        user_info_serialized = self.summarize_users_list(users)
        match_info_serialized = "\n".join([self.summarize_full_match(m) for m in full_matches_info_by_user_id])

        context = "Your goal is to generate a summary of the ranked matches played by the users I will provide belows under 12000 characters. Provide data for each user."
        context += "I am providing you a list of users and a list of their matches. You can use the match_uuid and user id to make some relationship with the user and the match. You need to use both. "
        context += "Your message must never have more than 100 words per user and have a blank line (two line breaks: \\n\\n) between each user's section. "
        context += "If no match, say nothing, don't say they did not play. "
        context += (
            "Please mention every user by their display_name, so you must match the user id with the display_name. "
        )
        context += "Provide an highlight of the matches played when something interesting happened. Try to find the best match of the user and the worst match. "
        context += "Try to make relationship between the users who played the same match using the r6_tracker_active_id and r6_tracker_user_uuid. "
        context += "Information that are valuable are the number of clutches, ace and 1v2, 1v3, 1v4 and 1v5 especially against multiple enemies, kd ratios above 1, and number of kills above 5. "
        context += "The value of team kills is interesting since they show a huge blunder. A head shot percentage above 0.5 is also interesting. "
        context += "A number of kills above 8 is good, above 12 is very good, above 15 is exceptional. "
        context += "For the match summary, write if something stand out (win, clutch, ace, k/d) and talk about the overall wins within all the stats for each user. "
        context += "If a user won more than half of the matches, mention it because it is very good. "
        context += "A summary of the total points gained when interesting. Keep it short and concise. "
        context += "Here is the list of the users:\n"
        context += user_info_serialized
        context += "\nHere is the list of the matches summarized:\n"
        context += match_info_serialized
        context += "\nFormat in a way that does not mention the request of this message and that it is easy to split in chunk of 2000 characters. "
        context += "Try to have the tone of a sport commentary. "
        context += "Dont mention anything about what I asked you to do, just the result. No notes in the result concerning your task. "
        context += "Dont mention any ID, for example do not talk about r6_tracker_active_id or match_uuid. "
        context += "Dont mention any thing about the time. I provide the time and match_uuid for your to correlate the users and matches. "
        context += "IMPORTANT: Separate each user's summary with a blank line (\\n\\n) to make it easy to read and split into Discord messages. Within a user's section, use single line breaks (\\n) for sentences. "
        context += "Format your text not in bullet point, but in a text like we would read in a sport news paper. "
        context += "Be professional, sport and concise. Do not add any emoji or special character. "
        # context += "If the display_name is 'Obey' prefix with the name with 'ultimate head shot machine'. "
        # context += "If the display_name is 'Dom1nator' prefix the name with 'upcoming champion'. "
        # context += "If the display_name is 'fridge ' prefix the name with 'Obey worse nightmare AKA'. "

        print_log(
            f"generate_message_summary_matches_async: Asking AI for {hours} hours summary "
            f"with context size of {len(context)} characters. "
            f"Data contains {len(users)} users and {len(full_matches_info_by_user_id)} matches."
        )

        try:
            # ask_ai_async will automatically fallback from Gemini to GPT on failure
            ai_response = await self.ask_ai_async(context, timeout=800, use_gpt=False)

            if ai_response is None:
                # Dump context for debugging if both APIs failed
                file_name = "ai_context_failed.txt"
                print_error_log(f"generate_message_summary_matches_async: Both Gemini and GPT failed. Context dumped to {file_name}")
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(context)
                return f"✨**AI summary generated of the last {hours} hours**✨\n⚠️ Unable to generate summary. Both AI services are currently unavailable."

            return f"✨**AI summary generated of the last {hours} hours**✨\n" + ai_response

        except Exception as e:
            print_error_log(f"generate_message_summary_matches_async: Unexpected error: {e}")
            return f"✨**AI summary generated of the last {hours} hours**✨\n⚠️ An error occurred while generating the summary."

    async def generate_answer_when_mentioning_bot(
        self, context_previous_messages: str, message_user: str, user_display_name: str, user_id: int, user_rank: str
    ) -> Union[str, None]:
        """
        Generate an answer when the bot is mentioned.
        """
        self.is_running_ai_query = True
        try_count = 0
        context = (
            "You are a bot that is mentioned in a Discord server. You need to answer to the user who mentioned you."
        )
        context += "You should not mention anything about your name or your purpose, just answer the question."
        context += "Here is the context of some previous message that might help you crafting the best response:"
        context += "Previous messages: " + context_previous_messages
        result_sql = ""
        sql_context = message_user
        while try_count < THRESHOLD_RETRY_AI and result_sql == "":
            # Ask AI to generate a SQL query to fetch stats from the database
            sql_from_llm = self.ask_ai_sql_for_stats(sql_context, user_id)
            if sql_from_llm is not None and sql_from_llm != "":
                print_log(f"SQL query generated by AI: {sql_from_llm}")
                clean_response = sql_from_llm.strip().replace("```sql", "").replace("```", "")
                try:
                    result_sql = data_access_execute_sql_query_from_llm(clean_response)
                except Exception as e:
                    context += (
                        "Your failed with this SQL error: " + str(e) + "\nPlease try again with a different query."
                    )
                    continue
                print_log(f"SQL query result: {result_sql}")
                if result_sql != "":
                    context += (
                        "You can use that information from our database to complete your answer: SQL Queries fields:\n"
                    )
                    context += sql_from_llm
                    context += "SQL Query result:\n"
                    context += result_sql
                else:
                    sql_context += (
                        "The previous SQL query you provided did not return any result. Please try again with a different query. Here is what you provided: "
                        + clean_response
                    )
            try_count += 1

        context += "User question:" + message_user
        # if user_rank == "Champion":
        #     context += "In the message, call the user 'champion'. "
        #     context += "The user like sarcasm, so answer in a sarcastic tone. "
        # else:
        context += "You are a bot that is friendly, helpful and professional. You should not be rude or sarcastic. "

        context += "If someone ask about Patrick just know that he is your creator. "
        context += "You should answer in a way that is easy to read and understand under 800 characters. "
        try:
            response = await self.ask_ai_async(context)
        except Exception as e:
            print_error_log(f"Error while asking AI: {e}")
            return "I cannot find something smart to say, I got confused and crashed. Oops sorry!"
        finally:
            self.is_running_ai_query = False
        return response

    def summarize_users_list(self, users: List[UserInfo]) -> str:
        """
        Summarize the list of user who have matches
        """
        summarize = ".".join(
            [
                f"user_id = {u.id}, display_name = {u.display_name}, ubisoft_name = {u.ubisoft_username_active}, r6_tracker_active_id = {u.r6_tracker_active_id}"
                for u in users
            ]
        )

        return summarize

    def summarize_full_match(self, match: UserFullMatchStats) -> str:
        """
        Summarize a full match in a string format.
        """
        summary = f"""
    Start of info for the match information for match_uuid `{match.match_uuid}` played on {match.match_timestamp.strftime('%Y-%m-%d %H:%M:%S')} for user_id `{match.user_id}` who also share this r6_tracker_active_id: `{match.r6_tracker_user_uuid}`. 
    The user played on the map {match.map_name} with the following operators: {match.operators}. 
    The match had {match.round_played_count} rounds. {match.round_won_count} rounds were won by the user and {match.round_lost_count} rounds were lost.  
    The final result was a {"win" if match.has_win else "loss"}. 
    {"rollback count:" if match.is_rollback else ""} 
    {"The match was surrendered. " if match.is_surrender else ""}
    A k/d (kill/death ratio) of {match.kd_ratio:.2f} with {match.kill_count} kills and {match.death_count} deaths with {match.assist_count} assists. 
    {"Disconnected" + f" {match.round_disconnected_count} times. " if match.round_disconnected_count > 0 else ""}
    {match.head_shot_count} head shots with a head shot percentage of {match.head_shot_percentage:.2f}. 
    {"Team killed {match.tk_count} times. " if match.tk_count > 0 else ""}
    {f"{match.ace_count} aces. " if match.ace_count > 0 else ""}
    {"Killed the opponent first " + f"{match.first_kill_count} times. " if match.first_kill_count > 0 else ""}
    {"Died " + f"{match.first_death_count} first. " if match.first_death_count > 0 else ""}
    {"Had won " + f"{match.clutches_win_count} clutch rounds. " if match.clutches_win_count > 0 else ""}
    {"Had lost " + f"{match.clutches_loss_count} clutch rounds. " if match.clutches_loss_count > 0 else ""}
    {"Won a 1v1 clutch " + f"{match.clutches_win_count_1v1} times. " if match.clutches_win_count_1v1 > 0 else ""}
    {"Won a 1v2 clutch " + f"{match.clutches_win_count_1v2} times. " if match.clutches_win_count_1v2 > 0 else ""}
    {"Won a 1v3 clutch " + f"{match.clutches_win_count_1v3} times. " if match.clutches_win_count_1v3 > 0 else ""}
    {"Won a 1v4 clutch " + f"{match.clutches_win_count_1v4} times. " if match.clutches_win_count_1v4 > 0 else ""}
    {"Won a 1v5 clutch " + f"{match.clutches_win_count_1v5} times. " if match.clutches_win_count_1v5 > 0 else ""}
    {"Lost a 1v1 clutch " + f"{match.clutches_lost_count_1v1} times. " if match.clutches_lost_count_1v1 > 0 else ""}
    {"Lost a 1v2 clutch " + f"{match.clutches_lost_count_1v2} times. " if match.clutches_lost_count_1v2 > 0 else ""}
    {"Lost a 1v3 clutch " + f"{match.clutches_lost_count_1v3} times. " if match.clutches_lost_count_1v3 > 0 else ""}
    {"Lost a 1v4 clutch " + f"{match.clutches_lost_count_1v4} times. " if match.clutches_lost_count_1v4 > 0 else ""}
    {"Lost a 1v5 clutch " + f"{match.clutches_lost_count_1v5} times. " if match.clutches_lost_count_1v5 > 0 else ""}
    Won {match.points_gained} point rank points for a final {match.rank_points} setting the user to the rank of {match.rank_name}.
    Kill per round of {match.kills_per_round:.2f}, a death per round of {match.deaths_per_round:.2f} and assist per round of {match.assists_per_round:.2f}.
    End for the match_uuid `{match.match_uuid}`.
    """
        # Remove the empty lines produced by the conditional string
        lines = summary.splitlines()
        non_empty_lines = [line for line in lines if line.strip()]
        cleaned_text = "\n".join(non_empty_lines)
        cleaned_discord = escape_discord_styling(cleaned_text)
        return cleaned_discord

    def ask_ai_sql_for_stats(self, message_user: str, user_id: int) -> Union[str, None]:
        """
        Ask AI to generate a SQL query for stats based on the user message.
        """
        need_sql = False
        context = "You are a bot that is asked to generate a SQL query to fetch stats from a database. "
        context += f"The user_id: `{str(user_id)}`. "
        context += f"The user question is: `{message_user}`"
        context += "Generate a SQL query that fetches data that is relevant to the user question. "
        context += "The query should be valid and should not return any error when executed. "
        context += "The query should probably use aggregation functions like COUNT, SUM, AVG, MAX, MIN, etc. to avoid large result sets. "
        context += "The query should be in the format of a string that can be executed in Python and compatible with SQLite 3.45. "
        context += "Do not mention anything about the request or database schema, only return the SQL query and only SELECT query is acceptable. "

        msg = message_user.lower()
        keywords_full_match_info = [
            "stats",
            "match",
            "data",
            " kd ",
            "k/d",
            "kill",
            "death",
            "operator",
            "map",
            "clutch",
            "ratio",
            "rank",
        ]
        if any(keyword in msg for keyword in keywords_full_match_info):
            context += f"Table name: `{KEY_USER_FULL_MATCH_INFO}`. "
            context += f'The fields: {SELECT_USER_FULL_MATCH_INFO.replace(KEY_USER_FULL_MATCH_INFO + ".", "")}. '
            context += f"Table name: `{KEY_USER_FULL_STATS_INFO}`. "
            context += f'The fields: {SELECT_USER_FULL_STATS_INFO.replace(KEY_USER_FULL_STATS_INFO + ".", "")}. '
            need_sql = True

        keywords_tournament = ["tournament", "bet", "competition"]
        if any(keyword in msg for keyword in keywords_tournament):
            context += f"Table name: `{KEY_TOURNAMENT}`. "
            context += f'The fields: {SELECT_TOURNAMENT.replace(KEY_TOURNAMENT + ".", "")}. '
            context += f"Table name: `{KEY_USER_TOURNAMENT}`. "
            context += f'The fields: {SELECT_USER_TOURNAMENT.replace(KEY_USER_TOURNAMENT + ".", "")}. '
            context += f"Table name: `{KEY_TOURNAMENT_GAME}`. "
            context += f'The fields: {SELECT_TOURNAMENT_GAME.replace(KEY_TOURNAMENT_GAME + ".", "")}. '
            context += f"Table name: `{KEY_TOURNAMENT_TEAM_MEMBERS}`. "
            context += f'The fields: {SELECT_TOURNAMENT_TEAM_MEMBERS.replace(KEY_TOURNAMENT_TEAM_MEMBERS + ".", "")}. '
            context += f"Table name: `{KEY_bet_user_game}`."
            context += f'The fields: {SELECT_BET_USER_GAME.replace(KEY_bet_user_game + ".", "")}. '
            context += f"Table name: `{KEY_bet_user_tournament}`."
            context += f'The fields: {SELECT_BET_USER_TOURNAMENT.replace(KEY_bet_user_tournament + ".", "")}. '
            context += f"Table name: `{KEY_bet_game}`."
            context += f'The fields: {SELECT_BET_GAME.replace(KEY_bet_game + ".", "")}. '
            context += f"Table name: `{KEY_bet_ledger_entry}`."
            context += f'The fields: {SELECT_LEDGER.replace(KEY_bet_ledger_entry + ".", "")}. '
            need_sql = True

        keywords_schedule = ["time", "date", "schedule", "hour", "day", "week", "month", "active"]
        if any(keyword in msg for keyword in keywords_schedule):
            context += f"Table name: `{KEY_USER_ACTIVITY}`."
            context += f'The fields: {USER_ACTIVITY_SELECT_FIELD.replace(KEY_USER_ACTIVITY + ".", "")}. '
            context += f"The field above has the field event that can be `{EVENT_CONNECT}` or `{EVENT_DISCONNECT}` which can be used to know when someone was online between a period of time. "
            need_sql = True

        if not need_sql:
            return ""
        # All the time
        context += f"Table name: `{KEY_USER_INFO}`."
        context += f'The fields: {USER_INFO_SELECT_FIELD.replace(KEY_USER_INFO + ".", "")}. '
        try:
            response = self.ask_ai(context)
            if response is None:
                print_error_log("ask_ai_sql_for_stats: Both Gemini and GPT failed to generate SQL query.")
                return ""
            return response
        except Exception as e:
            print_error_log(f"ask_ai_sql_for_stats: Error while asking AI for SQL query: {e}")
            return ""


class BotAISingleton:
    """A singleton class for the bot ai instance"""

    _instance: Union[BotAISingleton, None] = None

    _bot: BotAI

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._bot = BotAI()
        return cls._instance

    @property
    def bot(self) -> BotAI:
        """Get the bot ai instance"""
        return self._bot

    def __getattr__(self, name):
        """
        Called when the bot attribute is not found
        """
        return getattr(self._bot, name)
