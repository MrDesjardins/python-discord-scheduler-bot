from datetime import datetime, timedelta
import asyncio


class RateLimiter:
    """The rate limiter wraps function avoiding frequent calls. Useful to avoid spamming the Discord API"""

    def __init__(self, interval_seconds):
        self.interval_seconds = interval_seconds
        self.last_called = datetime.min
        self.lock = asyncio.Lock()

    async def _call_function(self, func, *args, **kwargs):
        async with self.lock:
            now = datetime.now()
            if now - self.last_called < timedelta(seconds=self.interval_seconds):
                print(f"Skipping function {func.__name__} at {now}")
                return  # Skip execution if within the interval
            self.last_called = now
            # Ensure func is awaited correctly
            print(f"Calling function {func.__name__} at {now}")
            # if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
            # else:
            #     func(*args, **kwargs)

    async def __call__(self, func, *args, **kwargs):
        await self._call_function(func, *args, **kwargs)
