"""Browser manipulation functions"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import random
from typing import List

from deps.data_access_data_class import UserInfo
from deps.browser_context_manager import BrowserContextManager
from deps.models import UserFullMatchInfo, UserQueueForStats, UserWithUserMatchInfo
from deps.log import print_error_log


async def run_in_executor(func, *args):
    """
    Run in another thread the function
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, func, *args)


async def download_full_matches(users: List[UserQueueForStats]) -> List[UserWithUserMatchInfo]:
    """
    Download the maximum information for matches with the goal to persist the data into the database
    """
    all_users_matches: List[UserWithUserMatchInfo] = []
    # Before the loop, start the browser and do a request to the R6 tracker to get the cookies
    # Then, in the loop, use the cookies to get the stats using the API
    try:
        with BrowserContextManager() as context:
            for user in users:
                try:
                    matches: List[UserFullMatchInfo] = context.download_full_matches(user.user_info)
                    all_users_matches.append(UserWithUserMatchInfo(user, matches))

                    if len(users) > 1:
                        await asyncio.sleep(random.uniform(0.5, 2))  # Sleep 0.5 to 2 seconds between each request

                except Exception as e:
                    print_error_log(
                        f"post_queued_user_stats: Error getting the user ({user.user_info.display_name}) stats from R6 tracker: {e}"
                    )
                    continue  # Skip to the next user
    except Exception as e:
        print_error_log(f"post_queued_user_stats: Error opening the browser context: {e}")
    return all_users_matches


async def download_full_matches_async(users: List[UserInfo], post_process_callback=None):
    """
    Run the blocking download_full_matches in another thread and perform a post-processing task
    in the main thread after completion.
    """

    def blocking_task():
        # Run the long-running function (must be made synchronous)
        return asyncio.run(download_full_matches(users))

    try:
        # Offload the blocking task to a thread
        loop = asyncio.get_event_loop()
        matches = await loop.run_in_executor(None, blocking_task)
    except Exception as e:
        print_error_log(f"download_full_matches_async: Error during match download: {e}")
        return []

    try:
        if post_process_callback:
            # Schedule the callback back on the main thread
            loop.call_soon(asyncio.create_task, post_process_callback(users, matches))

        return matches
    except Exception as e:
        print_error_log(f"download_full_matches_async: callback: {e}")
        return []
