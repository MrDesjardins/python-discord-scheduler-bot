"""Browser manipulation functions"""

import asyncio
import random
import time
from typing import List, Union
from deps.browser_context_manager import BrowserContextManager
from deps.models import (
    UserFullMatchStats,
    UserInformation,
    UserQueueForStats,
    UserWithUserInformation,
    UserWithUserMatchInfo,
)
from deps.log import print_error_log


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
                        time.sleep(random.uniform(1, 5))  # Sleep few seconds between each request

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
