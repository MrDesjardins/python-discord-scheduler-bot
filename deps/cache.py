
import asyncio
import time
from typing import Callable, Awaitable, Union, Optional
import inspect
import dill as pickle
import atexit

CACHE_FILE = "cache.txt"
ALWAYS_TTL = 60*60*24*365*10

class CacheItem:
    def __init__(self, value, ttl):
        self.value = value
        self.expiry = time.time() + ttl


class TTLCache:
    def __init__(self, default_ttl=60):
        self.cache = {}
        self.default_ttl = default_ttl
        self.lock = asyncio.Lock()

    def _is_expired(self, key):
        item = self.cache.get(key, None)
        if not item:
            return True
        if time.time() > item.expiry:
            del self.cache[key]
            return True
        return False

    def set(self, key, value, ttl=None):
        if ttl is None:
            ttl = self.default_ttl
        self.cache[key] = CacheItem(value, ttl)

    def get(self, key):
        if self._is_expired(key):
            return None
        return self.cache.get(key).value

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        self.cache.clear()

    async def _cleanup(self):
        while True:
            expired_keys = []
            for key in list(self.cache.keys()):
                if self._is_expired(key):
                    expired_keys.append(key)
            for key in expired_keys:
                del self.cache[key]
            await asyncio.sleep(1)  # Adjust the sleep time as needed

    def start_cleanup(self):
        asyncio.create_task(self._cleanup())

    def initialize(self, values):
        if values:
            self.cache = values



async def getCache(inMemory: bool, key: str, fetch_function: Optional[Union[Callable[[], Awaitable], Callable[[], str]]] = None):
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
    #         else:
    #             print(f"Value {key} not found by api")
    # else:
    #     print(f"Value {key} found in cache")
    return value


def setCache(inMemory: bool, key: str, value: any, cache_seconds: Optional[int] = None):
    if inMemory:
        memoryCache.set(key, value, cache_seconds)
    else:
        dataCache.set(key, value, cache_seconds)
        save_to_file(dataCache.cache, CACHE_FILE)


def save_to_file(obj, filename):
    with open(filename, 'wb') as file:
        pickle.dump(obj, file)


def load_from_file(filename):
    try:
        with open(filename, 'rb') as file:
            return pickle.load(file)
    except FileNotFoundError:
        return None


def on_exit():
    print("Script is exiting, saving the object...")
    save_to_file(dataCache.cache, CACHE_FILE)


memoryCache = TTLCache(default_ttl=60)  # Cache with 60 seconds TTL
dataCache = TTLCache(default_ttl=60)  # Cache with 60 seconds TTL
dataCache.initialize(load_from_file(CACHE_FILE))

# Register the on_exit function to be called when the script exits
atexit.register(on_exit)
