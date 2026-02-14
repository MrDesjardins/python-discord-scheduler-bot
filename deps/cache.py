"""Cache value for the bot. It acts as the persistent storage for the bot to store the data that needs to be kept between restarts."""

import dataclasses
import asyncio
import time
from typing import Callable, Awaitable, List, Union, Optional, Any
import inspect
import threading

from deps.cache_data_access import (
    clear_expired_cache,
    get_value,
    remove_key,
    remove_key_by_prefix,
    set_value,
)
from deps.log import print_log

ALWAYS_TTL = 60 * 60 * 24 * 365 * 10
ONE_YEAR_TTL = 60 * 60 * 24 * 365
ONE_MONTH_TTL = 60 * 60 * 24 * 30
THREE_DAY_TTL = 60 * 60 * 24 * 3
ONE_DAY_TTL = 60 * 60 * 24
ONE_HOUR_TTL = 60 * 60 * 1
DEFAULT_TTL = 60


@dataclasses.dataclass
class CacheItem:
    """Represents an item in the cache with an expiry time"""

    def __init__(self, value: Any, ttl_in_seconds: int):
        self.value = value
        self.expiry = time.time() + ttl_in_seconds


class TTLCache:
    """A simple in-memory cache with time-to-live (TTL) support"""

    def __init__(self, default_ttl_in_seconds=60) -> None:
        self.cache: dict[str, Any] = {}
        self.default_ttl = default_ttl_in_seconds

    def _is_expired(self, key: str) -> bool:
        """Check if the cache item with the given key is expired"""
        item = self.cache.get(key, None)
        if not item:
            return True
        if time.time() > item.expiry:
            del self.cache[key]
            return True
        return False

    def set(self, key: str, value: Any, ttl_in_seconds: Optional[int] = None) -> None:
        """Set the value in the cache with an optional TTL"""
        if ttl_in_seconds is None:
            ttl_in_seconds = self.default_ttl
        self.cache[key] = CacheItem(value, ttl_in_seconds)

    def get(self, key: str) -> Union[Optional[Any]]:
        """Get the value from the cache if it exists and is not expired"""
        if self._is_expired(key):
            return None
        existing_value: Union[CacheItem, None] = self.cache.get(key)
        if existing_value is None:
            return None
        return existing_value.value

    def delete(self, key: str) -> None:
        """Delete the value from the cache"""
        if key in self.cache:
            del self.cache[key]

    def delete_by_prefix(self, prefix: str) -> int:
        """Delete all keys that start with the given prefix"""
        counter = 0
        keys_to_delete = [key for key in self.cache if key.startswith(prefix)]
        for key in keys_to_delete:
            del self.cache[key]
            counter += 1
        return counter

    def clear(self) -> None:
        """Delete ALL the cache"""
        self.cache.clear()

    async def _cleanup(self) -> None:
        """Remove expired key."""
        while True:
            expired_keys: List[str] = []
            for key in list(self.cache.keys()):
                if self._is_expired(key):
                    expired_keys.append(key)
            for key in expired_keys:
                if key in self.cache:
                    del self.cache[key]
            await asyncio.sleep(10000)  # Adjust the sleep time as needed

    def start_cleanup(self) -> None:
        """Start the task to clean up in the background."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, daemon=True).start()

        asyncio.run_coroutine_threadsafe(self._cleanup(), loop)


def remove_cache(in_memory: bool, key: str) -> None:
    """Remove the key from the cache"""
    if in_memory:
        memoryCache.delete(key)
    else:
        remove_key(key)


async def get_cache(
    in_memory: bool,
    key: str,
    fetch_function: Optional[Union[Callable[[], Awaitable], Callable[[], Any]]] = None,
    ttl_in_seconds: Optional[int] = None,
) -> Any:
    """Get the value from the cache from the in-memory or data cache
    If the value is not in the cache, calls the fetch function to get the value and set it into the cache
    """
    if in_memory:
        value = memoryCache.get(key)
    else:
        value = get_value(key)

    if value is None and fetch_function:
        # Check if the fetch function itself is an async function
        if inspect.iscoroutinefunction(fetch_function):
            value = await fetch_function()
        else:
            value = fetch_function()

        if value:
            if in_memory:
                memoryCache.set(key, value, ttl_in_seconds)
            else:
                set_value(key, value, ttl_in_seconds)
    return value


def set_cache(in_memory: bool, key: str, value: Any, cache_seconds: Optional[int] = None):
    """Set the value in the cache in the in-memory or data cache
    If the cache is on disk, the data goes into the file as well
    """
    if in_memory:
        memoryCache.set(key, value, cache_seconds)
    else:
        set_value(key, value, cache_seconds)


def reset_cache_by_prefixes(prefixes: List[str]) -> None:
    """Reset the cache for the given GUID"""

    for prefix in prefixes:
        del_memory_count = memoryCache.delete_by_prefix(prefix)
        del_file_count = remove_key_by_prefix(prefix)
        print_log(
            f"Deleted {del_memory_count} from memory and {del_file_count} from the persisted cache for prefix {prefix}"
        )


def start_periodic_cache_cleanup():
    """Start the periodic cache cleanup task"""
    return asyncio.create_task(periodic_cache_cleanup())  # Schedule the cleanup task


async def periodic_cache_cleanup():
    """Periodically clean up the cache"""
    while True:
        clear_expired_cache()  # Make sure this function is defined elsewhere

        await asyncio.sleep(60)  # Adjust the sleep time as needed


memoryCache = TTLCache(default_ttl_in_seconds=DEFAULT_TTL)
memoryCache.start_cleanup()
