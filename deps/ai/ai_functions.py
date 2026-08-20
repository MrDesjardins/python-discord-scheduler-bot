"""
Generate message for the matches played by the users
"""

from __future__ import annotations  # Enables forward reference resolution
from datetime import datetime, timedelta, timezone
import os
import asyncio
import time
import re
import json
from uuid import uuid4
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
    fetch_user_info,
)
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats
from deps.log import print_ai_audit_log, print_error_log, print_log
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
from deps.ai.graph_functions import (
    GraphResponse,
    looks_like_graph_request,
    render_graph,
    validate_graph_plan,
)

load_dotenv()

THRESHOLD_GEMINI = 500
THRESHOLD_RETRY_AI = 2
OPENAI_FALLBACK_MODELS = ["gpt-5.6-terra", "gpt-5.6-luna"]
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

    def _start_ai_audit(self, question: str, request_type: str, metadata: dict | None = None) -> str:
        """Record the exact prompt before sending it to an AI provider."""
        request_id = uuid4().hex[:12]
        print_ai_audit_log(
            request_id=request_id,
            phase="prompt",
            request_type=request_type,
            content=question,
            metadata=metadata,
        )
        return request_id

    def _finish_ai_audit(
        self, request_id: str, request_type: str, response: str | None, provider: str
    ) -> None:
        """Record the provider and exact response for a previously logged prompt."""
        print_ai_audit_log(
            request_id=request_id,
            phase="response",
            request_type=request_type,
            content=response,
            provider=provider,
        )

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

            for model in OPENAI_FALLBACK_MODELS:
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

    def ask_ai(
        self, question: str, use_gpt: bool = False, request_type: str = "general"
    ) -> Union[str, None]:
        """
        Ask AI a question and return the answer (blocking).
        Automatically falls back from Gemini to GPT on failure.
        """
        request_id = self._start_ai_audit(
            question,
            request_type,
            {"use_gpt": use_gpt, "daily_count": self.today_count()},
        )
        print_log(f"ask_ai: The number of AI count today is {self.today_count()} (request {request_id}).")

        should_try_gemini = not use_gpt and self.today_count() < THRESHOLD_GEMINI

        if should_try_gemini:
            print_log("ask_ai: Will try Gemini (gemini-2.5-flash) first, then fallback to OpenAI")
        else:
            print_log("ask_ai: Will use OpenAI directly (Gemini threshold exceeded or GPT requested)")

        if should_try_gemini:
            result = self._try_gemini(question)
            if result is not None:
                self._finish_ai_audit(request_id, request_type, result, "gemini-2.5-flash")
                return result

        result = self._try_openai(question)
        self._finish_ai_audit(request_id, request_type, result, "openai")
        return result

    async def ask_ai_async(
        self,
        question: str,
        timeout: float = 800.0,
        use_gpt: bool = False,
        gemini_timeout: float = 120.0,
        request_type: str = "general",
    ) -> Union[str, None]:
        """
        Ask AI a question and return the answer (non-blocking, async, with timeout).
        Gemini and OpenAI run in separate thread phases with independent asyncio timeouts;
        total wall time is capped by ``timeout``.
        """
        self.increase_daily_count()
        request_id = self._start_ai_audit(
            question,
            request_type,
            {"use_gpt": use_gpt, "daily_count": self.today_count()},
        )
        try:
            print_log(
                f"ask_ai_async: The number of AI count today is {self.today_count()} "
                f"(request {request_id})."
            )

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
                            self._finish_ai_audit(request_id, request_type, result, "gemini-2.5-flash")
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
                self._finish_ai_audit(request_id, request_type, None, "timeout-before-openai")
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
                self._finish_ai_audit(request_id, request_type, result, "openai")
                return result
            except asyncio.TimeoutError:
                print_error_log(
                    f"ask_ai_async: OpenAI phase timed out after {openai_phase_budget:.1f}s "
                    f"(total cap {timeout}s)."
                )
                self._finish_ai_audit(request_id, request_type, None, "openai-timeout")
                return None
        except Exception as e:
            print_error_log(f"ask_ai_async: Unexpected error during AI API call: {e}")
            self._finish_ai_audit(request_id, request_type, None, "error")
            return None

    def gather_information_for_generating_message_summary(
        self, hours, guild_id: int | None = None
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
        if guild_id is None:
            users: List[UserInfo] = get_active_user_info(from_time, to_time)
        else:
            users = get_active_user_info(from_time, to_time, guild_id=guild_id)
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
        users, full_matches_info_by_user_id = self.gather_information_for_generating_message_summary(
            hours, guild_id=guild_id
        )
        if len(users) == 0 or len(full_matches_info_by_user_id) == 0:
            return f"✨**AI summary generated of the last {hours} hours**✨\nNo user played any match in the last {hours} hours."
        print_log(f"Users display name {', '.join([u.display_name for u in users])}")

        user_info_serialized = self.summarize_users_list(users)
        context_before_matches = "Your goal is to generate a summary of the ranked matches played by the users below, kept concise. Provide one section per user."
        context_before_matches += "The canonical public identity is canonical_ubisoft_name. Use that exact name in the response; discord_display_name is only an alias for disambiguation. Never invent, shorten, or substitute a name. "
        context_before_matches += "The identity records and verified summary facts are authoritative. Match records are evidence for specific highlights. "
        context_before_matches += "You can use match_uuid and user_id to correlate users and matches, but never print IDs. "
        context_before_matches += "Your message must never have more than 100 words per user and have a blank line (two line breaks: \\n\\n) between each user's section. "
        context_before_matches += "If no match, say nothing, don't say they did not play. "
        context_before_matches += (
            "Mention every user who has match data by their canonical Ubisoft name. "
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
        context_before_matches += "\n"
        context_before_matches += self.build_verified_daily_facts(users, full_matches_info_by_user_id)
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
        context_after_matches += "Before returning, verify that every player name exactly matches a canonical_ubisoft_name in the identity records. "
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
            ai_response = await self.ask_ai_async(
                context, timeout=800, use_gpt=False, request_type="daily_summary"
            )

            if ai_response is None:
                # Dump context for debugging if both APIs failed
                file_name = "ai_context_failed.txt"
                print_error_log(
                    f"generate_message_summary_matches_async: Both Gemini and GPT failed. Context dumped to {file_name}"
                )
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(context)
                return f"✨**AI summary generated of the last {hours} hours**✨\n⚠️ Unable to generate summary. Both AI services are currently unavailable."

            ai_response = self.normalize_user_names_in_response(ai_response, users)
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
    ) -> Union[str, GraphResponse, None]:
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
        resolved_query_users = self.resolve_users_in_text(message_user, resolved_mentions)
        if resolved_query_users and not resolved_mentions:
            context += "The application resolved these identities from the user's text. Use them exactly and do not infer other users. "
            context += "Resolved identities: " + self.summarize_users_list(resolved_query_users)
        if resolved_mentions:
            context += "The current question already has these user mentions resolved. "
            context += "Use these exact identities only and never merge them together. "
            context += "Do not invent nicknames, aliases, or descriptors unless the permanent server knowledge explicitly defines one for that resolved user. "
            context += "Resolved mentions: " + self.summarize_users_list(resolved_mentions)

        if looks_like_graph_request(message_user):
            graph_response = await self.generate_graph_response(
                guild_id, message_user, user_id, resolved_query_users
            )
            if graph_response is not None:
                self.is_running_ai_query = False
                return graph_response

        result_sql = ""
        sql_context = message_user
        while try_count < THRESHOLD_RETRY_AI and result_sql == "":
            # Ask AI to generate a SQL query to fetch stats from the database
            sql_from_llm = await self.ask_ai_sql_for_stats(
                guild_id, sql_context, user_id, resolved_query_users
            )
            if sql_from_llm is not None and sql_from_llm != "":
                print_log(f"SQL query generated by AI: {sql_from_llm}")
                clean_response = sql_from_llm.strip().replace("```sql", "").replace("```", "")
                try:
                    result_sql = data_access_execute_sql_query_from_llm(clean_response)
                except Exception as e:
                    context += (
                        "Your failed with this SQL error: " + str(e) + "\nPlease try again with a different query."
                    )
                    try_count += 1
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
        context += "Use exact canonical Ubisoft names for resolved users; Discord display names are aliases only. "
        context += "If permanent server knowledge explicitly defines a title or alias for one of those resolved users, you may apply it to that exact user only. "
        context += "Otherwise do not invent titles, descriptors, or nicknames. "
        context += "You should answer in a way that is easy to read and understand under 800 characters. "
        try:
            context = await self.apply_guild_ai_context(guild_id, context)
            response = await self.ask_ai_async(context, request_type="mention_response")
        except Exception as e:
            print_error_log(f"Error while asking AI: {e}")
            return "I cannot find something smart to say, I got confused and crashed. Oops sorry!"
        finally:
            self.is_running_ai_query = False
        if response is not None:
            response = self.normalize_user_names_in_response(response, resolved_query_users)
        return response

    async def generate_graph_response(
        self,
        guild_id: int | None,
        message_user: str,
        requester_id: int,
        resolved_users: List[UserInfo],
    ) -> GraphResponse | None:
        """Plan and render a graph without executing model-generated Python."""
        prompt = (
            "Classify this Discord request as a graph request. Return JSON only. "
            "Use this schema: {needs_graph:boolean, chart_type:line|bar|stacked_bar|area|scatter|null, "
            "metric:voice_time|kd_ratio, group_by:month|week, user_ids:integer[], months:integer, title:string|null}. "
            "voice_time means time connected to voice channels. kd_ratio means total kills divided by total deaths "
            "for each period; use weekly grouping when the user asks for weekly K/D. Exclude periods with zero deaths. "
            "Use the requester ID for 'my' or 'me'. Use explicitly resolved user IDs exactly. "
            "Choose line for time trends, bar for comparisons, and stacked_bar for multiple users. "
            "If the request does not ask for a graph, set needs_graph to false.\n"
            f"Requester user_id: {requester_id}\n"
            f"User question: {message_user}\n"
        )
        if resolved_users:
            prompt += "Resolved identities (IDs are authoritative):\n" + self.summarize_users_list(resolved_users)
        try:
            prompt = await self.apply_guild_ai_context(guild_id, prompt)
            raw_plan = self.ask_ai(prompt, request_type="graph_plan")
            parsed_plan = self.parse_query_plan(raw_plan)
            # parse_query_plan handles the common JSON contract but graph plans use
            # a different top-level key, so parse the same tolerant response format.
            if parsed_plan is None:
                cleaned = (raw_plan or "").strip().replace("```json", "").replace("```", "").strip()
                parsed_plan = json.loads(cleaned)
            plan = validate_graph_plan(
                parsed_plan, requester_id, [user.id for user in resolved_users]
            )
            if not plan["user_ids"]:
                plan["user_ids"] = [requester_id]
            return render_graph(plan, guild_id)
        except Exception as error:
            print_error_log(f"generate_graph_response: Graph request fallback: {error}")
            return None

    def summarize_users_list(self, users: List[UserInfo]) -> str:
        """
        Summarize the list of user who have matches
        """
        summarize = "\n".join(
            [
                "Identity record: "
                f"user_id={u.id}; canonical_ubisoft_name={u.ubisoft_username_active or u.ubisoft_username_max or 'unknown'}; "
                f"discord_display_name={u.display_name}; display_name = {u.display_name}; "
                f"ubisoft_name = {u.ubisoft_username_active or u.ubisoft_username_max or 'unknown'}; "
                f"main_ubisoft_name={u.ubisoft_username_max or 'unknown'}; "
                f"r6_tracker_uuid={u.r6_tracker_active_id or 'unknown'}"
                for u in users
            ]
        )

        return summarize

    def resolve_users_in_text(
        self, message: str, resolved_mentions: List[UserInfo]
    ) -> List[UserInfo]:
        """Resolve textual names to database identities before asking the model for SQL."""
        users_by_id = {user.id: user for user in resolved_mentions}
        normalized_message = message.casefold()
        for user in fetch_user_info().values():
            aliases = {
                alias.strip()
                for alias in (
                    user.display_name,
                    user.ubisoft_username_active,
                    user.ubisoft_username_max,
                )
                if alias and alias.strip()
            }
            if any(re.search(rf"(?<!\w){re.escape(alias.casefold())}(?!\w)", normalized_message) for alias in aliases):
                users_by_id[user.id] = user
        return list(users_by_id.values())

    def normalize_user_names_in_response(self, response: str, users: List[UserInfo]) -> str:
        """Replace known Discord aliases with the canonical Ubisoft name in final prose."""
        normalized = response
        replacements: list[tuple[str, str]] = []
        for user in users:
            canonical = user.ubisoft_username_active or user.ubisoft_username_max or user.display_name
            for alias in (user.display_name, user.ubisoft_username_max):
                if alias and alias.casefold() != canonical.casefold():
                    replacements.append((alias, canonical))
        for alias, canonical in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
            normalized = re.sub(
                rf"(?<!\w){re.escape(alias)}(?!\w)", canonical, normalized, flags=re.IGNORECASE
            )
        return normalized

    def validate_generated_sql(
        self,
        sql: str,
        resolved_users: List[UserInfo],
        require_canonical_identity: bool = False,
        require_kd_semantics: bool = False,
    ) -> str:
        """Reject identity-unsafe SQL before it reaches the database."""
        clean_sql = sql.strip().replace("```sql", "").replace("```", "").strip()
        lowered = clean_sql.casefold()
        if not (lowered.startswith("select") or lowered.startswith("with")):
            raise ValueError("AI generated a non-read-only SQL statement")
        if lowered.startswith("with") and re.search(r"\b(insert|update|delete|replace)\b", lowered):
            raise ValueError("WITH queries may only contain a final SELECT")
        if ";" in clean_sql.rstrip(";"):
            raise ValueError("AI generated multiple SQL statements")
        if require_canonical_identity:
            if "user_info" not in lowered:
                raise ValueError("Leaderboard/partner SQL must join user_info for canonical names")
            if "ubisoft_username_active" not in lowered and "ubisoft_username_max" not in lowered:
                raise ValueError("SQL must select a canonical Ubisoft username")
            if "display_name" in lowered:
                raise ValueError("SQL must not use Discord display_name as the answer identity")
        if require_kd_semantics:
            if "999999" in lowered:
                raise ValueError("K/D SQL must not use an artificial zero-death K/D value")
        for user in resolved_users:
            display_name = (user.display_name or "").casefold()
            if display_name and re.search(
                rf"ubisoft_username\s*=\s*['\"]{re.escape(display_name)}['\"]", lowered
            ):
                raise ValueError(
                    f"AI used Discord display name {user.display_name!r} as a Ubisoft username"
                )
            if ("user_full_match_info" in lowered or "user_info" in lowered) and str(user.id) not in clean_sql:
                raise ValueError(
                    f"AI query did not use resolved user_id {user.id} for {user.display_name!r}"
                )
        return clean_sql

    def parse_query_plan(self, response: str | None) -> dict | None:
        """Parse the deliberately small JSON contract used before SQL generation."""
        if not response:
            return None
        cleaned = response.strip().replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Be tolerant when a provider adds a short explanation around the JSON.
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return None
        if not isinstance(parsed, dict) or not isinstance(parsed.get("needs_sql"), bool):
            return None
        return parsed

    def validate_query_plan(
        self, plan: dict, user_id: int, resolved_users: List[UserInfo]
    ) -> dict:
        """Normalize the plan and reject unsafe or unsupported planning output."""
        allowed_domains = {"matches", "tournaments", "bets", "activity", "general"}
        domain = plan.get("domain", "general")
        if domain not in allowed_domains:
            raise ValueError(f"Unsupported query-plan domain: {domain}")

        user_ids = plan.get("user_ids", [])
        if not isinstance(user_ids, list) or not all(isinstance(value, int) for value in user_ids):
            raise ValueError("Query-plan user_ids must be a list of integers")
        resolved_ids = {user.id for user in resolved_users}
        if resolved_ids and not resolved_ids.issubset(set(user_ids)):
            raise ValueError("Query plan omitted one or more explicitly resolved users")

        metrics = plan.get("metrics", [])
        if not isinstance(metrics, list) or not all(isinstance(value, str) for value in metrics):
            raise ValueError("Query-plan metrics must be a list of strings")

        limit = plan.get("limit", 25)
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Query-plan limit must be between 1 and 100")

        normalized = dict(plan)
        normalized["domain"] = domain
        normalized["user_ids"] = list(dict.fromkeys(user_ids))
        normalized["metrics"] = metrics
        normalized["limit"] = limit
        return normalized

    def build_query_plan_prompt(
        self, message_user: str, user_id: int, resolved_mentions: List[UserInfo]
    ) -> str:
        """Build a compact prompt that separates intent recognition from SQL syntax."""
        prompt = (
            "Classify the user's request for a Discord bot database lookup. Return JSON only. "
            "If the question can be answered without database data, set needs_sql to false. "
            "Otherwise set needs_sql to true and describe only the requested facts. "
            "Never invent names or IDs. Explicitly resolved users must all be included by numeric ID. "
            "Use this exact schema: {needs_sql: boolean, domain: matches|tournaments|bets|activity|general, "
            "user_ids: integer[], metrics: string[], time_range: string|null, group_by: string[], "
            "sort_by: string|null, limit: integer}."
        )
        prompt += f"\nRequester user_id: {user_id}\nUser question: {message_user}"
        if resolved_mentions:
            prompt += "\nExplicitly resolved users (IDs are authoritative):\n"
            prompt += self.summarize_users_list(resolved_mentions)
        return prompt

    def build_verified_daily_facts(
        self, users: List[UserInfo], matches: List[UserFullMatchStats]
    ) -> str:
        """Build deterministic totals so the model narrates verified facts."""
        names = {user.id: user.ubisoft_username_active or user.ubisoft_username_max or user.display_name for user in users}
        grouped: dict[int, list[UserFullMatchStats]] = {user.id: [] for user in users}
        for match in matches:
            grouped.setdefault(match.user_id, []).append(match)

        lines = ["Verified summary facts (do not recalculate or contradict these values):"]
        for user in users:
            user_matches = grouped.get(user.id, [])
            if not user_matches:
                continue
            wins = sum(1 for match in user_matches if match.has_win)
            total_kills = sum(match.kill_count for match in user_matches)
            total_deaths = sum(match.death_count for match in user_matches)
            best = max(user_matches, key=self.daily_summary_match_score)
            worst = min(user_matches, key=self.daily_summary_match_score)
            lines.append(
                f"- {names[user.id]} (user_id={user.id}): {len(user_matches)} matches, "
                f"{wins} wins, {len(user_matches) - wins} losses, {total_kills} kills, "
                f"{total_deaths} deaths, best_match_uuid={best.match_uuid}, worst_match_uuid={worst.match_uuid}"
            )
        shared_matches: dict[str, set[int]] = {}
        for match in matches:
            shared_matches.setdefault(match.match_uuid, set()).add(match.user_id)
        shared = [
            f"{match_uuid} ({', '.join(names.get(user_id, str(user_id)) for user_id in user_ids)})"
            for match_uuid, user_ids in shared_matches.items()
            if len(user_ids) > 1
        ]
        if shared:
            lines.append("- Shared match groups: " + "; ".join(shared))
        return "\n".join(lines)

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
        # Also resolve plain-text names here. The Discord event path normally supplies
        # resolved mentions, but this keeps direct callers and tests safe as well.
        resolved_mentions = self.resolve_users_in_text(message_user, resolved_mentions)
        need_sql = False
        context = "You are a bot that is asked to generate a SQL query to fetch stats from a database. "
        context += f"The user_id: `{str(user_id)}`. "
        context += f"The user question is: `{message_user}`"
        context += "Generate a SQL query that fetches data that is relevant to the user question. "
        context += "The query should be valid and should not return any error when executed. "
        context += "The query should probably use aggregation functions like COUNT, SUM, AVG, MAX, MIN, etc. to avoid large result sets. "
        context += "The query should be in the format of a string that can be executed in Python and compatible with SQLite 3.45. "
        context += "Do not mention anything about the request or database schema, only return the SQL query and only SELECT query is acceptable. "
        context += "Identity safety rule: never use a Discord display name or a guessed name as a value for user_full_match_info.ubisoft_username. "
        context += "When a resolved identity is supplied, filter by its numeric user_id or join to user_info by id. Never invent an identity literal. "
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
            "win",
            "loss",
            "played",
            "best",
            "better",
            "average",
            "total",
            "recent",
            "how many",
        ]
        if any(keyword in msg for keyword in keywords_full_match_info):
            context += f"Table name: `{KEY_USER_FULL_MATCH_INFO}`. "
            context += f'The fields: {SELECT_USER_FULL_MATCH_INFO.replace(KEY_USER_FULL_MATCH_INFO + ".", "")}. '
            context += f"Table name: `{KEY_USER_FULL_STATS_INFO}`. "
            context += f'The fields: {SELECT_USER_FULL_STATS_INFO.replace(KEY_USER_FULL_STATS_INFO + ".", "")}. '
            need_sql = True

        requires_canonical_identity = bool(
            re.search(r"\b(best|top|leaderboard)\b", msg)
            or "partner" in msg
            or "played with" in msg
        )
        requires_kd_semantics = bool(re.search(r"(?<!\w)k\s*/?\s*d(?!\w)", msg))
        if requires_kd_semantics:
            context += (
                "K/D rule: calculate player K/D as SUM(kill_count) / SUM(death_count), "
                "or use the verified kd_ratio field when the question is match-level. "
                "For aggregate leaderboards exclude groups with SUM(death_count) = 0, "
                "and never use an artificial infinite K/D. "
                "For leaderboards, join user_info and select COALESCE(user_info.ubisoft_username_active, "
                "user_info.ubisoft_username_max) as the canonical player name. "
            )
        if requires_canonical_identity:
            context += (
                "Identity output rule: never select display_name or user_full_match_info.ubisoft_username. "
                "Join user_info by numeric user_id and return the canonical Ubisoft username fields. "
            )

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

        # First ask for intent, independently from SQL syntax. This keeps ordinary
        # conversational questions on the normal answer path and gives SQL generation
        # a small, validated contract to follow.
        plan = None
        try:
            plan_prompt = await self.apply_guild_ai_context(
                guild_id, self.build_query_plan_prompt(message_user, user_id, resolved_mentions)
            )
            raw_plan = self.ask_ai(plan_prompt, request_type="query_plan")
            parsed_plan = self.parse_query_plan(raw_plan)
            if parsed_plan is not None and not parsed_plan["needs_sql"]:
                print_log("ask_ai_sql_for_stats: query plan determined that SQL is unnecessary")
                return ""
            if parsed_plan is not None:
                plan = self.validate_query_plan(parsed_plan, user_id, resolved_mentions)
        except Exception as e:
            # A plan provider failure must not prevent the existing SQL path from
            # answering a statistics question. The free-form path is the fallback.
            print_error_log(f"ask_ai_sql_for_stats: Query-plan fallback: {e}")

        # All the time
        context += f"Table name: `{KEY_USER_INFO}`."
        context += f'The fields: {USER_INFO_SELECT_FIELD.replace(KEY_USER_INFO + ".", "")}. '
        if plan is not None:
            context += (
                "Validated query plan (follow this intent exactly; do not add unrequested users or metrics): "
                + json.dumps(plan, sort_keys=True)
                + ". "
            )
        try:
            context = await self.apply_guild_ai_context(guild_id, context)
            validation_feedback = ""
            for attempt in range(THRESHOLD_RETRY_AI):
                attempt_context = context
                if validation_feedback:
                    attempt_context += (
                        " Previous SQL attempt was rejected by the application: "
                        + validation_feedback
                        + " Regenerate the query while fixing that exact issue."
                    )
                response = self.ask_ai(attempt_context, request_type="sql_generation")
                if response is None:
                    print_error_log("ask_ai_sql_for_stats: AI failed to generate SQL query.")
                    return ""
                try:
                    clean_response = self.validate_generated_sql(
                        response,
                        resolved_mentions,
                        require_canonical_identity=requires_canonical_identity,
                        require_kd_semantics=requires_kd_semantics,
                    )
                    if plan is not None:
                        for planned_user_id in plan["user_ids"]:
                            if str(planned_user_id) not in clean_response:
                                raise ValueError(
                                    f"SQL omitted planned user_id {planned_user_id}"
                                )
                    return clean_response
                except ValueError as e:
                    validation_feedback = str(e)
                    print_error_log(
                        f"ask_ai_sql_for_stats: SQL validation failed on attempt {attempt + 1}: {e}"
                    )
            return ""
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
