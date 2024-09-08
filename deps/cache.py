
import asyncio
import time
from typing import Callable, Awaitable, List, Union, Optional, Any
import inspect
import dill as pickle
import atexit

CACHE_FILE = "cache.txt"
ALWAYS_TTL = 60*60*24*365*10
DEFAULT_TTL = 60

KEY_DAILY_MSG = "DailyMessageSentInChannel"
KEY_REACTION_USERS = "ReactionUsers"
KEY_GUILD_USERS_AUTO_SCHEDULE = "GuildUsersAutoScheduleDay"
KEY_GUILD_CHANNEL = "GuildAdminConfigChannel"
KEY_MESSAGE = "Message"
KEY_USER = "User"
KEY_GUILD = "Guild"
KEY_MEMBER = "Member"


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
        if ttl is None:
            ttl = self.default_ttl
        self.cache[key] = CacheItem(value, ttl)

    def get(self, key: str) -> Union[Optional[Any]]:
        if self._is_expired(key):
            return None
        return self.cache.get(key).value

    def delete(self, key: str) -> None:
        if key in self.cache:
            del self.cache[key]

    def delete_by_prefix(self, prefix: str) -> int:
        counter = 0
        keys_to_delete = [key for key in self.cache if key.startswith(prefix)]
        for key in keys_to_delete:
            del self.cache[key]
            counter += 1
        return counter

    def clear(self) -> None:
        self.cache.clear()

    async def _cleanup(self) -> None:
        while True:
            expired_keys: List[str] = []
            for key in list(self.cache.keys()):
                if self._is_expired(key):
                    expired_keys.append(key)
            for key in expired_keys:
                del self.cache[key]
            await asyncio.sleep(100)  # Adjust the sleep time as needed

    def start_cleanup(self) -> None:
        asyncio.create_task(self._cleanup())

    def initialize(self, values: dict[str, Any]) -> None:
        """ Initialize the cache from the data persistent storage """
        if values:
            self.cache = values


async def getCache(inMemory: bool, key: str, fetch_function: Optional[Union[Callable[[], Awaitable], Callable[[], str]]] = None) -> Any:
    """ Get the value from the cache from the in-memory or data cache 
    If the value is not in the cache, calls the fetch function to get the value and set it into the cache
    """
    if inMemory:
        cache = memoryCache
    else:
        cache = dataCache
    value = cache.get(key)
    if not value:
        if fetch_function:
            # Check if the fetch function is asynchronous
            result = fetch_function()
            if inspect.isawaitable(result):
                value = await result
            else:
                value = result
            if value:
                cache.set(key, value)
    return value


def setCache(inMemory: bool, key: str, value: Any, cache_seconds: Optional[int] = None):
    """ Set the value in the cache in the in-memory or data cache 
    If the cache is on disk, the data goes into the file as well
    """
    if inMemory:
        memoryCache.set(key, value, cache_seconds)
    else:
        dataCache.set(key, value, cache_seconds)
        save_to_file(dataCache.cache, CACHE_FILE)


def reset_cache_for_guid(guild_id: int) -> None:
    """ Reset the cache for the given GUID """
    prefixes = [f"{KEY_DAILY_MSG}:{guild_id}",
                f"{KEY_REACTION_USERS}:{guild_id}",
                f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{guild_id}",
                f"{KEY_GUILD_CHANNEL}:{guild_id}",
                f"{KEY_MESSAGE}:{guild_id}",
                f"{KEY_USER}:{guild_id}",
                f"{KEY_GUILD}:{guild_id}",
                f"{KEY_MEMBER}:{guild_id}",
                ]
    for prefix in prefixes:
        del_memory_count = memoryCache.delete_by_prefix(prefix)
        del_file_count = dataCache.delete_by_prefix(prefix)
        print(
            f"Deleted {del_memory_count} from memory and {del_file_count} from file for prefix {prefix}")
    save_to_file(dataCache.cache, CACHE_FILE)


def save_to_file(obj: dict[str, any], filename: str) -> None:
    """ Binary saving of the content of the object to the file """
    with open(filename, 'wb') as file:
        pickle.dump(obj, file)


def load_from_file(filename: str) -> Optional[dict[str, any]]:
    try:
        with open(filename, 'rb') as file:
            return pickle.load(file)
    except FileNotFoundError:
        return None


def on_exit() -> None:
    """ Ensure when leaving the script that we save the data to a file """
    print("Script is exiting, saving the object...")
    save_to_file(dataCache.cache, CACHE_FILE)


memoryCache = TTLCache(default_ttl_in_seconds=DEFAULT_TTL)
dataCache = TTLCache(default_ttl_in_seconds=DEFAULT_TTL)
dataCache.initialize(load_from_file(CACHE_FILE))

# Register the on_exit function to be called when the script exits
atexit.register(on_exit)
