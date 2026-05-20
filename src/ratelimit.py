import asyncio
import time
from collections import defaultdict, deque
from typing import Dict


class RateLimiter:
    """Sliding-window rate limiter safe for concurrent async callers."""

    def __init__(self, max_requests: int = 5000, time_window: int = 3600):
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, key: str = "default") -> bool:
        async with self._locks[key]:
            now = time.time()
            requests = self._requests[key]

            while requests and requests[0] <= now - self.time_window:
                requests.popleft()

            if len(requests) < self.max_requests:
                requests.append(now)
                return True
            return False

    async def wait_if_needed(self, key: str = "default") -> None:
        while not await self.acquire(key):
            oldest = self._requests[key][0] if self._requests[key] else time.time()
            wait_time = (oldest + self.time_window) - time.time()
            if wait_time > 0:
                await asyncio.sleep(min(wait_time, 60))


github_rate_limiter = RateLimiter(max_requests=5000, time_window=3600)
