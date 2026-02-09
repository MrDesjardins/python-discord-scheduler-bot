"""Browser manipulation functions"""

import asyncio
import random
import time
from typing import List, Union
from deps.browser_context_manager import BrowserContextManager
from deps.data_access_data_class import UserInfo
from deps.models import (
    UserFullMatchStats,
    UserInformation,
    UserQueueForStats,
    UserWithUserInformation,
    UserWithUserMatchInfo,
)
from deps.log import print_error_log, print_log


def download_full_matches(users_queued: List[UserQueueForStats]) -> List[UserWithUserMatchInfo]:
    """
    Download the maximum information for matches with the goal to persist the data into the database
    """
    all_users_matches: List[UserWithUserMatchInfo] = []
    # Before the loop, start the browser and do a request to the R6 tracker to get the cookies
    # Then, in the loop, use the cookies to get the stats using the API
    try:
        with BrowserContextManager() as context:
            for user_queue in users_queued:
                try:
                    matches: List[UserFullMatchStats] = context.download_full_matches(user_queue)
                    all_users_matches.append(UserWithUserMatchInfo(user_queue, matches))

                    if len(users_queued) > 1:
                        time.sleep(random.uniform(1, 5))  # Sleep few seconds between each request

                except Exception as e:
                    print_error_log(
                        f"post_queued_user_stats: Error getting the user ({user_queue.user_info.display_name}) stats from R6 tracker: {e}"
                    )
                    continue  # Skip to the next user
    except Exception as e:
        print_error_log(f"post_queued_user_stats: Error opening the browser context: {e}")
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

                    if len(users_queued) > 1:
                        time.sleep(random.uniform(3, 12))  # Sleep few seconds between each request

                except Exception as e:
                    print_error_log(
                        f"download_full_user_information: Error getting the user ({user_queue.user_info.display_name}) stats from R6 tracker: {e}"
                    )
                    continue  # Skip to the next user
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


def download_operator_stats_for_users(users: List[UserInfo]) -> List[tuple[UserInfo, List]]:
    """
    Download operator statistics for a list of users using BrowserContextManager.
    Returns list of tuples: (UserInfo, operator_stats_data)
    """
    all_operator_stats = []

    try:
        with BrowserContextManager() as context:
            for i, user in enumerate(users):
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

                    # Rate limiting: sleep between requests (except for the last one)
                    if i < len(users) - 1:
                        sleep_time = random.uniform(8, 12)  # Random 8-12 seconds to avoid rate limiting
                        print_log(
                            f"download_operator_stats_for_users: Waiting {sleep_time:.1f} seconds before next request..."
                        )
                        time.sleep(sleep_time)

                except Exception as e:
                    print_error_log(
                        f"download_operator_stats_for_users: Error downloading stats for {user.display_name}: {e}"
                    )
                    continue

    except Exception as e:
        print_error_log(f"download_operator_stats_for_users: Error opening the browser context: {e}")

    return all_operator_stats


async def download_operator_stats_for_users_async(users: List[UserInfo]) -> List[tuple[UserInfo, List]]:
    """
    Run the blocking download_operator_stats_for_users in another thread.
    """
    try:
        # Offload the blocking task to a thread
        return await asyncio.to_thread(download_operator_stats_for_users, users)
    except Exception as e:
        print_error_log(f"download_operator_stats_for_users_async: Error during operator stats download: {e}")
        return []
