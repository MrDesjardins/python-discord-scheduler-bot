"""
Generate message for the matches played by the users
"""

from __future__ import annotations  # Enables forward reference resolution
from datetime import datetime, timedelta, timezone
import os
import asyncio
import time
from typing import List, Union
from dotenv import load_dotenv
from google import genai
from google.genai import types
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
    data_access_get_guild_ai_context,
    data_access_set_guild_ai_context,
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

THRESHOLD_GEMINI = 500
THRESHOLD_RETRY_AI = 5
# Gemini SDK HTTP timeout in milliseconds (large prompts; avoids stuck sockets indefinitely)
GEMINI_HTTP_TIMEOUT_MS = 4 * 60 * 1000
DAILY_SUMMARY_MAX_CONTEXT_CHARS = 90_000


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

    async def get_guild_ai_context(self, guild_id: Union[int, None]) -> str:
        """
        Get the permanent AI context configured for the guild.
        """
        if guild_id is None:
            return ""
        current_context = await data_access_get_guild_ai_context(guild_id)
        if current_context is None:
            return ""
        return current_context.strip()

    async def apply_guild_ai_context(self, guild_id: Union[int, None], prompt: str) -> str:
        """
        Prepend guild permanent context to a prompt when available.
        """
        guild_context = await self.get_guild_ai_context(guild_id)
        if guild_context == "":
            return prompt

        composed_prompt = (
            "The following is permanent knowledge configured by the server administrators. "
            "Treat it as durable context that should inform your answer unless the user explicitly overrides it.\n"
            "Permanent server knowledge:\n"
        )
        composed_prompt += guild_context
        composed_prompt += "\n\nTask instructions:\n"
        composed_prompt += prompt
        return composed_prompt

    async def update_guild_ai_context(self, guild_id: int, instruction: str) -> Union[str, None]:
        """
        Use the AI to update the guild permanent context document from a natural-language instruction.
        Returns the updated full document text.
        """
        current_context = await self.get_guild_ai_context(guild_id)

        prompt = (
            "You are editing a permanent context document used by a Discord bot as server knowledge. "
            "Apply the moderator instruction to the current document. "
            "Keep unrelated knowledge unchanged. "
            "If the instruction asks to add something, add it only if it makes sense as durable server knowledge. "
            "If the instruction asks to remove or rewrite something, update only the relevant portion. "
            "Return only the full updated document as plain text with no code fences, no explanations, and no notes."
        )
        prompt += "\nCurrent document:\n"
        prompt += current_context if current_context != "" else "(empty)"
        prompt += "\nModerator instruction:\n"
        prompt += instruction

        updated_context = await self.ask_ai_async(prompt, timeout=800, use_gpt=False)
        if updated_context is None:
            return None

        cleaned_context = updated_context.replace("```text", "").replace("```", "").strip()
        data_access_set_guild_ai_context(guild_id, cleaned_context)
        persisted_context = await self.get_guild_ai_context(guild_id)
        if persisted_context is None:
            return None
        return persisted_context

    def today_count(self):
        """
        Get the current count of AI request
        """
        today_str = self.today_key()
        return self.request_counter_per_day.get(today_str, 0)

    def _try_gemini(self, question: str) -> Union[str, None]:
        """
        Blocking Gemini-only attempt. Returns text on success, None to signal fallback.
        """
        try:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                print_error_log("ask_ai: GEMINI_API_KEY not found in environment variables. Falling back to GPT.")
                return None
            key_len = len(gemini_key)
            prefix = gemini_key[:8] if key_len >= 8 else gemini_key
            print_log(f"ask_ai: GEMINI_API_KEY present: True, prefix: {prefix}... (len={key_len})")
            print_log("ask_ai: Attempting to use Gemini API (model: gemini-2.5-flash)...")
            client_gemini = genai.Client(
                api_key=gemini_key,
                http_options=types.HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS),
            )
            print_log("ask_ai: Calling Gemini generate_content...")
            t_call = time.monotonic()
            response_gemini = client_gemini.models.generate_content(
                model="gemini-2.5-flash", contents=question
            )
            elapsed = time.monotonic() - t_call
            print_log(f"ask_ai: Gemini generate_content finished in {elapsed:.2f}s")

            if hasattr(response_gemini, "text") and response_gemini.text:
                print_log("ask_ai: SUCCESS - Using Gemini (gemini-2.5-flash) API response.")
                return response_gemini.text
            print_error_log("ask_ai: Gemini response has no 'text' attribute or is empty. Falling back to GPT.")
            return None
        except Exception as e:
            print_error_log(f"ask_ai: Gemini API error ({type(e).__name__}): {e}. Falling back to GPT.")
            return None

    def _try_openai(self, question: str) -> Union[str, None]:
        """
        Blocking OpenAI-only attempt.
        """
        print_log("ask_ai: Attempting to use OpenAI GPT API...")
        print_log(f"ask_ai: OPENAI_API_KEY present: {bool(os.getenv('OPENAI_API_KEY'))}")
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            print_log(f"ask_ai: API key starts with: {openai_key[:10]}...")

        try:
            client_open_ai = OpenAI()
            models_to_try = ["gpt-4o", "gpt-3.5-turbo"]

            for model in models_to_try:
                try:
                    print_log(f"ask_ai: Trying OpenAI model: {model}")
                    response_open_ai = client_open_ai.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": question}],
                    )

                    if response_open_ai.choices and len(response_open_ai.choices) > 0:
                        result = response_open_ai.choices[0].message.content
                        print_log(f"ask_ai: SUCCESS - Using OpenAI {model} API response.")
                        return result
                    print_error_log(f"ask_ai: {model} response has no choices or is empty.")
                    continue

                except Exception as model_error:
                    error_str = str(model_error).lower()
                    print_error_log(f"ask_ai: {model} failed with error: {model_error}")
                    if "model" in error_str and (
                        "not found" in error_str or "access" in error_str or "permission" in error_str
                    ):
                        print_error_log(f"ask_ai: {model} not available, trying next model.")
                        continue
                    raise model_error

            print_error_log("ask_ai: All OpenAI models failed to return a valid response.")
            return None

        except Exception as e:
            print_error_log(f"ask_ai: OpenAI GPT API error: {e}")
            return None

    def ask_ai(self, question: str, use_gpt: bool = False) -> Union[str, None]:
        """
        Ask AI a question and return the answer (blocking).
        Automatically falls back from Gemini to GPT on failure.
        """
        print_log(f"ask_ai: The number of AI count today is {self.today_count()}.")

        should_try_gemini = not use_gpt and self.today_count() < THRESHOLD_GEMINI

        if should_try_gemini:
            print_log("ask_ai: Will try Gemini (gemini-2.5-flash) first, then fallback to OpenAI")
        else:
            print_log("ask_ai: Will use OpenAI directly (Gemini threshold exceeded or GPT requested)")

        if should_try_gemini:
            result = self._try_gemini(question)
            if result is not None:
                return result

        return self._try_openai(question)

    async def ask_ai_async(
        self,
        question: str,
        timeout: float = 800.0,
        use_gpt: bool = False,
        gemini_timeout: float = 120.0,
    ) -> Union[str, None]:
        """
        Ask AI a question and return the answer (non-blocking, async, with timeout).
        Gemini and OpenAI run in separate thread phases with independent asyncio timeouts;
        total wall time is capped by ``timeout``.
        """
        self.increase_daily_count()
        try:
            print_log(f"ask_ai_async: The number of AI count today is {self.today_count()}.")

            should_try_gemini = not use_gpt and self.today_count() < THRESHOLD_GEMINI
            if should_try_gemini:
                print_log(
                    "ask_ai_async: Will try Gemini first (phase timeout), then OpenAI if needed"
                )
            else:
                print_log("ask_ai_async: Will use OpenAI directly (Gemini skipped)")

            deadline = time.monotonic() + timeout

            if should_try_gemini:
                remaining = deadline - time.monotonic()
                phase_timeout = min(gemini_timeout, remaining) if remaining > 0 else 0.0
                if phase_timeout > 0:
                    try:
                        result = await asyncio.wait_for(
                            asyncio.to_thread(self._try_gemini, question),
                            timeout=phase_timeout,
                        )
                        if result is not None:
                            return result
                    except asyncio.TimeoutError:
                        print_error_log(
                            f"ask_ai_async: Gemini phase timed out after {phase_timeout:.1f}s, "
                            "falling back to OpenAI"
                        )
                elif remaining <= 0:
                    print_error_log("ask_ai_async: No time budget remaining for Gemini phase")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print_error_log(
                    f"ask_ai_async: Total timeout of {timeout}s reached before OpenAI phase could start"
                )
                return None

            openai_phase_budget = remaining
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._try_openai, question),
                    timeout=remaining,
                )
                if result is None:
                    print_error_log(
                        "ask_ai_async: Both Gemini and GPT APIs failed to return a valid response."
                    )
                return result
            except asyncio.TimeoutError:
                print_error_log(
                    f"ask_ai_async: OpenAI phase timed out after {openai_phase_budget:.1f}s "
                    f"(total cap {timeout}s)."
                )
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

    def daily_summary_match_score(self, match: UserFullMatchStats) -> float:
        """
        Rank matches by usefulness for the daily AI summary when the prompt needs trimming.
        """
        score = 0.0
        score += abs(match.points_gained) * 2
        score += match.kill_count
        score += match.assist_count * 0.5
        score += match.clutches_win_count * 10
        score += match.ace_count * 20
        score += match.tk_count * 8
        score += match.first_kill_count * 2
        score += match.first_death_count * 2
        score += max(match.kd_ratio - 1.0, 0) * 10
        if match.has_win:
            score += 5
        return score

    def summarize_matches_for_daily_summary(self, matches: List[UserFullMatchStats], max_chars: int) -> tuple[str, int]:
        """
        Serialize match records for the daily AI summary without exceeding a character budget.

        The OpenAI fallback has a tighter effective TPM/request limit than Gemini for this bot.
        Keep at least one notable match per user when possible, then spend the remaining budget
        on the most interesting matches.
        """
        if max_chars <= 0:
            return "", len(matches)

        summarized_matches = [(index, match, self.summarize_full_match(match)) for index, match in enumerate(matches)]
        total_match_chars = sum(len(summary) for _, _, summary in summarized_matches)
        total_match_chars += max(len(summarized_matches) - 1, 0)
        if total_match_chars <= max_chars:
            return "\n".join(summary for _, _, summary in summarized_matches), 0

        selected_indexes: set[int] = set()
        selected_length = 0

        def add_if_fits(index: int, summary: str) -> bool:
            nonlocal selected_length
            separator_length = 1 if selected_indexes else 0
            projected_length = selected_length + separator_length + len(summary)
            if projected_length > max_chars:
                return False
            selected_indexes.add(index)
            selected_length = projected_length
            return True

        best_match_by_user: dict[int, tuple[int, UserFullMatchStats, str]] = {}
        for index, match, summary in summarized_matches:
            current_best = best_match_by_user.get(match.user_id)
            if current_best is None or self.daily_summary_match_score(match) > self.daily_summary_match_score(
                current_best[1]
            ):
                best_match_by_user[match.user_id] = (index, match, summary)

        for index, _, summary in sorted(best_match_by_user.values(), key=lambda item: item[0]):
            add_if_fits(index, summary)

        remaining_matches = sorted(
            summarized_matches,
            key=lambda item: (self.daily_summary_match_score(item[1]), item[1].match_timestamp),
            reverse=True,
        )
        for index, _, summary in remaining_matches:
            if index in selected_indexes:
                continue
            add_if_fits(index, summary)

        omitted_count = len(matches) - len(selected_indexes)
        selected_text = "\n".join(summary for index, _, summary in summarized_matches if index in selected_indexes)
        omission_note = f"\n{omitted_count} lower-priority match records were omitted to keep this request under the AI fallback limit."
        if omitted_count > 0 and selected_length + len(omission_note) <= max_chars:
            selected_text += omission_note
        return selected_text, omitted_count

    async def generate_message_summary_matches_async(self, guild_id: Union[int, None], hours: int) -> str:
        """
        Async version: Generate a message summary of the matches played by the users without blocking the event loop.
        Uses automatic Gemini->GPT fallback from ask_ai_async.
        """
        users, full_matches_info_by_user_id = self.gather_information_for_generating_message_summary(hours)
        if len(users) == 0 or len(full_matches_info_by_user_id) == 0:
            return f"✨**AI summary generated of the last {hours} hours**✨\nNo user played any match in the last {hours} hours."
        print_log(f"Users display name {', '.join([u.display_name for u in users])}")

        user_info_serialized = self.summarize_users_list(users)
        context_before_matches = "Your goal is to generate a summary of the ranked matches played by the users I will provide belows under 12000 characters. Provide data for each user."
        context_before_matches += "I am providing you a list of users and a list of their matches. You can use the match_uuid and user id to make some relationship with the user and the match. You need to use both. "
        context_before_matches += "Your message must never have more than 100 words per user and have a blank line (two line breaks: \\n\\n) between each user's section. "
        context_before_matches += "If no match, say nothing, don't say they did not play. "
        context_before_matches += (
            "Please mention every user by their display_name, so you must match the user id with the display_name. "
        )
        context_before_matches += "Provide an highlight of the matches played when something interesting happened. Try to find the best match of the user and the worst match. "
        context_before_matches += "Try to make relationship between the users who played the same match using the r6_tracker_active_id and r6_tracker_user_uuid. "
        context_before_matches += "Information that are valuable are the number of clutches, ace and 1v2, 1v3, 1v4 and 1v5 especially against multiple enemies, kd ratios above 1, and number of kills above 5. "
        context_before_matches += "The value of team kills is interesting since they show a huge blunder. A head shot percentage above 0.5 is also interesting. "
        context_before_matches += "A number of kills above 8 is good, above 12 is very good, above 15 is exceptional. "
        context_before_matches += "For the match summary, write if something stand out (win, clutch, ace, k/d) and talk about the overall wins within all the stats for each user. "
        context_before_matches += "If a user won more than half of the matches, mention it because it is very good. "
        context_before_matches += "A summary of the total points gained when interesting. Keep it short and concise. "
        context_before_matches += "Here is the list of the users:\n"
        context_before_matches += user_info_serialized
        context_before_matches += "\nHere is the list of the matches summarized:\n"
        context_after_matches = "\nFormat in a way that does not mention the request of this message and that it is easy to split in chunk of 2000 characters. "
        context_after_matches += "Try to have the tone of a sport commentary. "
        context_after_matches += "Dont mention anything about what I asked you to do, just the result. No notes in the result concerning your task. "
        context_after_matches += (
            "Dont mention any ID, for example do not talk about r6_tracker_active_id or match_uuid. "
        )
        context_after_matches += "Dont mention any thing about the time. I provide the time and match_uuid for your to correlate the users and matches. "
        context_after_matches += "IMPORTANT: Separate each user's summary with a blank line (\\n\\n) to make it easy to read and split into Discord messages. Within a user's section, use single line breaks (\\n) for sentences. "
        context_after_matches += (
            "Format your text not in bullet point, but in a text like we would read in a sport news paper. "
        )
        context_after_matches += "Be professional, sport and concise. Do not add any emoji or special character. "
        # context += "If the display_name is 'Obey' prefix with the name with 'ultimate head shot machine'. "
        # context += "If the display_name is 'Dom1nator' prefix the name with 'upcoming champion'. "
        # context += "If the display_name is 'fridge ' prefix the name with 'Obey worse nightmare AKA'. "

        context_without_matches = await self.apply_guild_ai_context(
            guild_id, context_before_matches + context_after_matches
        )
        max_match_chars = DAILY_SUMMARY_MAX_CONTEXT_CHARS - len(context_without_matches)
        match_info_serialized, omitted_match_count = self.summarize_matches_for_daily_summary(
            full_matches_info_by_user_id, max_match_chars
        )
        if omitted_match_count > 0:
            print_log(
                f"generate_message_summary_matches_async: Omitted {omitted_match_count} "
                f"of {len(full_matches_info_by_user_id)} match records to keep context under "
                f"{DAILY_SUMMARY_MAX_CONTEXT_CHARS} characters."
            )

        context = context_before_matches + match_info_serialized + context_after_matches
        context = await self.apply_guild_ai_context(guild_id, context)

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
                print_error_log(
                    f"generate_message_summary_matches_async: Both Gemini and GPT failed. Context dumped to {file_name}"
                )
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(context)
                return f"✨**AI summary generated of the last {hours} hours**✨\n⚠️ Unable to generate summary. Both AI services are currently unavailable."

            return f"✨**AI summary generated of the last {hours} hours**✨\n" + ai_response

        except Exception as e:
            print_error_log(f"generate_message_summary_matches_async: Unexpected error: {e}")
            return f"✨**AI summary generated of the last {hours} hours**✨\n⚠️ An error occurred while generating the summary."

    async def generate_answer_when_mentioning_bot(
        self,
        guild_id: Union[int, None],
        context_previous_messages: str,
        message_user: str,
        resolved_mentions: List[UserInfo],
        user_display_name: str,
        user_id: int,
        user_rank: str,
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
        if resolved_mentions:
            context += "The current question already has these user mentions resolved. "
            context += "Use these exact identities only and never merge them together. "
            context += "Do not invent nicknames, aliases, or descriptors unless the permanent server knowledge explicitly defines one for that resolved user. "
            context += "Resolved mentions: " + self.summarize_users_list(resolved_mentions)
        result_sql = ""
        sql_context = message_user
        while try_count < THRESHOLD_RETRY_AI and result_sql == "":
            # Ask AI to generate a SQL query to fetch stats from the database
            sql_from_llm = await self.ask_ai_sql_for_stats(guild_id, sql_context, user_id, resolved_mentions)
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
        context += "Use exact resolved Discord display names for mentioned users as the canonical identity. "
        context += "If permanent server knowledge explicitly defines a title or alias for one of those resolved users, you may apply it to that exact user only. "
        context += "Otherwise do not invent titles, descriptors, or nicknames. "
        context += "You should answer in a way that is easy to read and understand under 800 characters. "
        try:
            context = await self.apply_guild_ai_context(guild_id, context)
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

    async def ask_ai_sql_for_stats(
        self,
        guild_id: Union[int, None],
        message_user: str,
        user_id: int,
        resolved_mentions: List[UserInfo],
    ) -> Union[str, None]:
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
        if resolved_mentions:
            resolved_user_ids = ",".join(str(user.id) for user in resolved_mentions)
            context += "The current question explicitly refers to these resolved users only. "
            context += "Do not guess additional identities, do not merge users, and use exact user ids when filtering. "
            context += f"Resolved mentioned users: {self.summarize_users_list(resolved_mentions)}. "
            context += f"When filtering by mentioned users, restrict to these user ids: {resolved_user_ids}. "

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
            context = await self.apply_guild_ai_context(guild_id, context)
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
