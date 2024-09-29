""" Cache value for the bot. It acts as the persistent storage for the bot to store the data that needs to be kept between restarts."""

import dataclasses
import asyncio
import time
from typing import Callable, Awaitable, List, Union, Optional, Any
import inspect
import atexit
import threading
import dill as pickle

CACHE_FILE = "cache.txt"
ALWAYS_TTL = 60 * 60 * 24 * 365 * 10
THREE_DAY_TTL = 60 * 60 * 24 * 3
DEFAULT_TTL = 60


@dataclasses.dataclass
class CacheItem:
    """Represents an item in the cache with an expiry time"""

    def __init__(self, value: Any, ttl_in_seconds: int):
        self.value = value
        self.expiry = time.time() + ttl_in_seconds


class TTLCache:
    """A simple in-memory cache with time-to-live (TTL) support"""

    def __init__(self, default_ttl_in_seconds=60):
        self.cache: dict[str, Any] = {}
        self.default_ttl = default_ttl_in_seconds
        self.lock = asyncio.Lock()

    def _is_expired(self, key: str) -> bool:
        """Check if the cache item with the given key is expired"""
        item = self.cache.get(key, None)
        if not item:
            return True
        if time.time() > item.expiry:
            del self.cache[key]
            return True
        return False

    def set(self, key: str, value: Any, ttl: Optional[str] = None):
        """Set the value in the cache with an optional TTL"""
        if ttl is None:
            ttl = self.default_ttl
        self.cache[key] = CacheItem(value, ttl)

    def get(self, key: str) -> Union[Optional[Any]]:
        """Get the value from the cache if it exists and is not expired"""
        if self._is_expired(key):
            return None
        return self.cache.get(key).value

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
            await asyncio.sleep(1000)  # Adjust the sleep time as needed

    def start_cleanup(self) -> None:
        """Start the task to clean up in the background."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, daemon=True).start()

        asyncio.run_coroutine_threadsafe(self._cleanup(), loop)

    def initialize(self, values: dict[str, Any]) -> None:
        """Initialize the cache from the data persistent storage"""
        if values:
            self.cache = values


def remove_cache(in_memory: bool, key: str) -> None:
    """Remove the key from the cache"""
    if in_memory:
        memoryCache.delete(key)
    else:
        dataCache.delete(key)
        save_to_file(dataCache.cache, CACHE_FILE)


async def get_cache(
    in_memory: bool,
    key: str,
    fetch_function: Optional[Union[Callable[[], Awaitable], Callable[[], str]]] = None,
) -> Any:
    """Get the value from the cache from the in-memory or data cache
    If the value is not in the cache, calls the fetch function to get the value and set it into the cache
    """
    cache = memoryCache if in_memory else dataCache
    value = cache.get(key)
    if not value and fetch_function:
        # Check if the fetch function itself is an async function
        if inspect.iscoroutinefunction(fetch_function):
            value = await fetch_function()
        else:
            value = fetch_function()

        if value:
            cache.set(key, value)
    return value


def set_cache(in_memory: bool, key: str, value: Any, cache_seconds: Optional[int] = None):
    """Set the value in the cache in the in-memory or data cache
    If the cache is on disk, the data goes into the file as well
    """
    if in_memory:
        memoryCache.set(key, value, cache_seconds)
    else:
        dataCache.set(key, value, cache_seconds)
        save_to_file(dataCache.cache, CACHE_FILE)


def reset_cache_by_prefixes(prefixes: List[str]) -> None:
    """Reset the cache for the given GUID"""

    for prefix in prefixes:
        del_memory_count = memoryCache.delete_by_prefix(prefix)
        del_file_count = dataCache.delete_by_prefix(prefix)
        print(f"Deleted {del_memory_count} from memory and {del_file_count} from file for prefix {prefix}")
    save_to_file(dataCache.cache, CACHE_FILE)


def save_to_file(obj: dict[str, any], filename: str) -> None:
    """Binary saving of the content of the object to the file"""
    with open(filename, "wb") as file:
        pickle.dump(obj, file)


def load_from_file(filename: str) -> Optional[dict[str, any]]:
    """Load the object from the file"""
    try:
        with open(filename, "rb") as file:
            return pickle.load(file)
    except FileNotFoundError:
        return None


def on_exit() -> None:
    """Ensure when leaving the script that we save the data to a file"""
    print("Script is exiting, saving the object...")
    save_to_file(dataCache.cache, CACHE_FILE)


memoryCache = TTLCache(default_ttl_in_seconds=DEFAULT_TTL)
dataCache = TTLCache(default_ttl_in_seconds=DEFAULT_TTL)
dataCache.initialize(load_from_file(CACHE_FILE))
memoryCache.start_cleanup()
dataCache.start_cleanup()

# Register the on_exit function to be called when the script exits
atexit.register(on_exit)
