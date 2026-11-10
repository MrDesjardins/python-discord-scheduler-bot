"""Browser manipulation functions"""

import asyncio
import os
from typing import Any, List, Union
from deps.browser_context_manager import BrowserContextManager
from deps.browser_exceptions import (
    BrowserException,
    BrowserLockContentionException,
    BrowserStartupException,
    BrowserTimeoutException,
    CircuitBreakerOpenException,
    TRACKER_UNAVAILABLE_EXCEPTIONS,
    TrackerAccountNotFoundException,
)
from deps.data_access_data_class import UserInfo
from deps.models import (
    UserFullMatchStats,
    UserInformation,
    UserQueueForStats,
    UserWithUserInformation,
    UserWithUserMatchInfo,
)
from deps.log import print_error_log, print_log, print_warning_log
from deps.stats_cc import StatsCCClient, StatsCCUnavailable


def download_full_matches(users_queued: List[UserQueueForStats]) -> List[UserWithUserMatchInfo]:
    """
    Download the maximum information for matches with the goal to persist the data into the database
    """
    all_users_matches: List[UserWithUserMatchInfo] = []
    # Explicit opt-in while stats.cc coverage is evaluated. Never turn absent
    # overlay telemetry into an empty history and a false "nobody played" report.
    if os.getenv("MATCH_STATS_PROVIDER", "tracker").lower() == "statscc":
        remaining = []
        with StatsCCClient() as client:
            for user_queue in users_queued:
                try:
                    matches = client.download_matches(user_queue.user_info)
                    all_users_matches.append(UserWithUserMatchInfo(user_queue, matches))
                except StatsCCUnavailable as exc:
                    print_warning_log(
                        f"download_full_matches: stats.cc unavailable for {user_queue.user_info.display_name}: {exc}"
                    )
                    remaining.append(user_queue)
        users_queued = remaining
        if not users_queued:
            return all_users_matches
    # Before the loop, start the browser and do a request to the R6 tracker to get the cookies
    # Then, in the loop, use the cookies to get the stats using the API
    try:
        with BrowserContextManager() as context:
            for user_queue in users_queued:
                try:
                    matches: List[UserFullMatchStats] = context.download_full_matches(user_queue)
                    all_users_matches.append(UserWithUserMatchInfo(user_queue, matches))
                except TRACKER_UNAVAILABLE_EXCEPTIONS:
                    raise  # Every remaining request would fail too
                except TrackerAccountNotFoundException as e:
                    # The username on file does not exist on tracker.gg (likely renamed).
                    # Record it (instead of just logging) so the caller can tell the member.
                    print_error_log(
                        f"download_full_matches: Account not found for {user_queue.user_info.display_name}: {e}"
                    )
                    all_users_matches.append(UserWithUserMatchInfo(user_queue, [], account_not_found=True))
                    continue
                except BrowserTimeoutException as e:
                    # Timeout for individual user - log and continue with next user
                    print_error_log(
                        f"download_full_matches: Timeout getting stats for {user_queue.user_info.display_name}: {e}"
                    )
                    continue
                except BrowserException as e:
                    # Other browser errors for individual user - log and continue
                    print_error_log(
                        f"download_full_matches: Error getting the user ({user_queue.user_info.display_name}) stats from R6 tracker: {e}"
                    )
                    continue  # Skip to the next user
    except TRACKER_UNAVAILABLE_EXCEPTIONS as e:
        # tracker.gg refuses every request until this is resolved; callers keep their work queued
        print_warning_log(f"download_full_matches: Stopping, {e}")
    except BrowserLockContentionException as e:
        # Browser busy with another task - users stay queued and retry next cycle
        print_warning_log(f"download_full_matches: Browser lock busy, will retry next cycle: {e}")
    except CircuitBreakerOpenException as e:
        # Circuit breaker open - abort all remaining users
        print_error_log(f"download_full_matches: Circuit breaker open, aborting: {e}")
    except BrowserStartupException as e:
        # Browser failed to start - abort all
        print_error_log(f"download_full_matches: Browser startup failed, aborting: {e}")
    except Exception as e:
        print_error_log(f"download_full_matches: Error opening the browser context: {e}")
    return all_users_matches


async def download_full_matches_async(users_queue_stats: List[UserQueueForStats]) -> List[UserWithUserMatchInfo]:
    """
    Run the blocking download_full_matches in another thread and perform a post-processing task
    in the main thread after completion.
    """
    try:
        # Offload the blocking task to a thread
        return await asyncio.to_thread(download_full_matches, users_queue_stats)
    except Exception as e:
        print_error_log(f"download_full_matches_async: Error during match download: {e}")
        return []


def download_full_user_information(users_queued: List[UserQueueForStats]) -> List[UserWithUserInformation]:
    """
    Download the maximum information for user with the goal to persist the data into the database
    """
    all_user_stats: List[UserWithUserInformation] = []
    # Before the loop, start the browser and do a request to the R6 tracker to get the cookies
    # Then, in the loop, use the cookies to get the stats using the API
    try:
        with BrowserContextManager() as context:
            for user_queue in users_queued:
                try:
                    user_info: Union[UserInformation, None] = context.download_full_user_information(user_queue)
                    if user_info is None:
                        print_error_log(
                            f"download_full_user_information: No user info found for {user_queue.user_info.display_name}"
                        )
                        continue
                    all_user_stats.append(UserWithUserInformation(user_queue, user_info))
                except TRACKER_UNAVAILABLE_EXCEPTIONS:
                    raise  # Every remaining request would fail too
                except BrowserTimeoutException as e:
                    # Timeout for individual user - log and continue with next user
                    print_error_log(
                        f"download_full_user_information: Timeout getting stats for {user_queue.user_info.display_name}: {e}"
                    )
                    continue
                except BrowserException as e:
                    # Other browser errors for individual user - log and continue
                    print_error_log(
                        f"download_full_user_information: Error getting the user ({user_queue.user_info.display_name}) stats from R6 tracker: {e}"
                    )
                    continue  # Skip to the next user
    except TRACKER_UNAVAILABLE_EXCEPTIONS as e:
        # tracker.gg refuses every request until this is resolved; callers keep their work queued
        print_warning_log(f"download_full_user_information: Stopping, {e}")
    except BrowserLockContentionException as e:
        # Browser busy with another task - callers can retry on their next cycle
        print_warning_log(f"download_full_user_information: Browser lock busy, will retry next cycle: {e}")
    except CircuitBreakerOpenException as e:
        # Circuit breaker open - abort all remaining users
        print_error_log(f"download_full_user_information: Circuit breaker open, aborting: {e}")
    except BrowserStartupException as e:
        # Browser failed to start - abort all
        print_error_log(f"download_full_user_information: Browser startup failed, aborting: {e}")
    except Exception as e:
        print_error_log(f"download_full_user_information: Error opening the browser context: {e}")
    return all_user_stats


async def download_full_user_information_async(
    users_queue_stats: List[UserQueueForStats],
) -> List[UserWithUserInformation]:
    """
    Run the blocking download_full_user_information in another thread and perform a post-processing task
    in the main thread after completion.
    """
    try:
        # Offload the blocking task to a thread
        return await asyncio.to_thread(download_full_user_information, users_queue_stats)
    except Exception as e:
        print_error_log(f"download_full_user_information_async: Error during match download: {e}")
        return []


def download_operator_stats_for_users(
    users: List[UserInfo],
) -> List[tuple[UserInfo, dict[str, Any]]]:
    """
    Download operator statistics for a list of users using BrowserContextManager.
    Returns list of tuples: (UserInfo, operator_stats_data)
    """
    all_operator_stats = []

    try:
        with BrowserContextManager() as context:
            for user in users:
                try:
                    # Skip users without R6 Tracker ID
                    if not user.r6_tracker_active_id:
                        print_log(f"download_operator_stats_for_users: Skipping {user.display_name} - no R6 Tracker ID")
                        continue

                    # Download operator stats
                    operator_data = context.download_operator_stats(user.r6_tracker_active_id)

                    if operator_data:
                        all_operator_stats.append((user, operator_data))
                        print_log(f"download_operator_stats_for_users: Downloaded stats for {user.display_name}")
                    else:
                        print_log(f"download_operator_stats_for_users: No stats found for {user.display_name}")
                except TRACKER_UNAVAILABLE_EXCEPTIONS:
                    raise  # Every remaining request would fail too
                except BrowserTimeoutException as e:
                    # Timeout for individual user - log and continue with next user
                    print_error_log(
                        f"download_operator_stats_for_users: Timeout downloading stats for {user.display_name}: {e}"
                    )
                    continue
                except BrowserException as e:
                    # Other browser errors for individual user - log and continue
                    print_error_log(
                        f"download_operator_stats_for_users: Error downloading stats for {user.display_name}: {e}"
                    )
                    continue

    except TRACKER_UNAVAILABLE_EXCEPTIONS as e:
        # tracker.gg refuses every request until this is resolved; callers keep their work queued
        print_warning_log(f"download_operator_stats_for_users: Stopping, {e}")
    except BrowserLockContentionException as e:
        # Browser busy with another task - callers can retry on their next cycle
        print_warning_log(f"download_operator_stats_for_users: Browser lock busy, will retry next cycle: {e}")
    except CircuitBreakerOpenException as e:
        # Circuit breaker open - abort all remaining users
        print_error_log(f"download_operator_stats_for_users: Circuit breaker open, aborting: {e}")
    except BrowserStartupException as e:
        # Browser failed to start - abort all
        print_error_log(f"download_operator_stats_for_users: Browser startup failed, aborting: {e}")
    except Exception as e:
        print_error_log(f"download_operator_stats_for_users: Error opening the browser context: {e}")

    return all_operator_stats


async def download_operator_stats_for_users_async(
    users: List[UserInfo],
) -> List[tuple[UserInfo, dict[str, Any]]]:
    """
    Run the blocking download_operator_stats_for_users in another thread.
    """
    try:
        # Offload the blocking task to a thread
        return await asyncio.to_thread(download_operator_stats_for_users, users)
    except Exception as e:
        print_error_log(f"download_operator_stats_for_users_async: Error during operator stats download: {e}")
        return []
