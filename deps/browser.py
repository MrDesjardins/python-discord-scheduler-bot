"""Browser manipulation functions"""

import asyncio
import inspect
import random
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


async def download_full_matches(users_queued: List[UserQueueForStats]) -> List[UserWithUserMatchInfo]:
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
                        await asyncio.sleep(random.uniform(1, 5))  # Sleep few seconds between each request

                except Exception as e:
                    print_error_log(
                        f"post_queued_user_stats: Error getting the user ({user_queue.user_info.display_name}) stats from R6 tracker: {e}"
                    )
                    continue  # Skip to the next user
    except Exception as e:
        print_error_log(f"post_queued_user_stats: Error opening the browser context: {e}")
    return all_users_matches


async def download_full_matches_async(users_queue_stats: List[UserQueueForStats], post_process_callback=None):
    """
    Run the blocking download_full_matches in another thread and perform a post-processing task
    in the main thread after completion.
    """

    def blocking_task():
        # Run the long-running function (must be made synchronous)
        return asyncio.run(download_full_matches(users_queue_stats))

    try:
        # Offload the blocking task to a thread
        list_users_and_matches: List[UserWithUserMatchInfo] = await asyncio.to_thread(blocking_task)
    except Exception as e:
        print_error_log(f"download_full_matches_async: Error during match download: {e}")
        return []

    try:
        if post_process_callback:
            # Schedule the callback back on the main thread
            if inspect.iscoroutinefunction(post_process_callback):
                await post_process_callback(list_users_and_matches)
            else:
                post_process_callback(list_users_and_matches)

        return list_users_and_matches
    except Exception as e:
        print_error_log(f"download_full_matches_async: callback: {e}")
        return []


async def download_full_user_information(users_queued: List[UserQueueForStats]) -> List[UserWithUserInformation]:
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
                        await asyncio.sleep(random.uniform(1, 5))  # Sleep few seconds between each request

                except Exception as e:
                    print_error_log(
                        f"post_queued_user_stats: Error getting the user ({user_queue.user_info.display_name}) stats from R6 tracker: {e}"
                    )
                    continue  # Skip to the next user
    except Exception as e:
        print_error_log(f"post_queued_user_stats: Error opening the browser context: {e}")
    return all_user_stats


async def download_full_user_information_async(users_queue_stats: List[UserQueueForStats], post_process_callback=None):
    """
    Run the blocking download_full_user_information in another thread and perform a post-processing task
    in the main thread after completion.
    """

    def blocking_task():
        # Run the long-running function (must be made synchronous)
        return asyncio.run(download_full_user_information(users_queue_stats))

    try:
        # Offload the blocking task to a thread
        list_user: List[UserWithUserInformation] = await asyncio.to_thread(blocking_task)
    except Exception as e:
        print_error_log(f"download_full_user_information_async: Error during match download: {e}")
        return []

    try:
        if post_process_callback:
            # Schedule the callback back on the main thread
            if inspect.iscoroutinefunction(post_process_callback):
                await post_process_callback(list_user)
            else:
                post_process_callback(list_user)

        return list_user
    except Exception as e:
        print_error_log(f"download_full_user_information_async: callback: {e}")
        return []
