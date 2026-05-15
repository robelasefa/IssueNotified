"""
Rate limiting module for GitHub API requests.
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict


class RateLimiter:
    """Rate limiter for GitHub API requests."""

    def __init__(self, max_requests: int = 5000, time_window: int = 3600):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per time window (GitHub default: 5000/hour)
            time_window: Time window in seconds (default: 3600 = 1 hour)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, key: str = "default") -> bool:
        """
        Acquire a rate limit slot.

        Args:
            key: Identifier for rate limit bucket

        Returns:
            True if request can proceed, False if rate limited
        """
        async with self.locks[key]:
            now = time.time()
            requests = self.requests[key]

            # Remove old requests outside time window
            while requests and requests[0] <= now - self.time_window:
                requests.popleft()

            # Check if we can make a new request
            if len(requests) < self.max_requests:
                requests.append(now)
                return True

            return False

    async def wait_if_needed(self, key: str = "default") -> None:
        """
        Wait if rate limit is exceeded.

        Args:
            key: Identifier for rate limit bucket
        """
        while not await self.acquire(key):
            # Calculate wait time until oldest request expires
            oldest_request = (
                self.requests[key][0] if self.requests[key] else time.time()
            )
            wait_time = (oldest_request + self.time_window) - time.time()

            if wait_time > 0:
                await asyncio.sleep(min(wait_time, 60))  # Wait max 60 seconds


# Global rate limiter instance
github_rate_limiter = RateLimiter(
    max_requests=5000, time_window=3600
)  # GitHub's rate limit
