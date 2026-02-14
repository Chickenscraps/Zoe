"""Token bucket rate limiter for Kraken REST API.

Kraken Intermediate tier: 20 tokens, refill 0.5/s.
Each REST call consumes 1 token (history calls may consume 2).

Usage:
    limiter = RateLimiter(capacity=20, refill_rate=0.5)
    await limiter.acquire()  # blocks if no tokens available
    # ... make REST call ...
"""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Async token bucket rate limiter."""

    def __init__(self, capacity: int = 20, refill_rate: float = 0.5):
        """
        Args:
            capacity: Maximum tokens in the bucket.
            refill_rate: Tokens added per second.
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens: float = float(capacity)
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

        # Stats
        self.total_acquired: int = 0
        self.total_waited: float = 0.0

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

    async def acquire(self, cost: int = 1) -> float:
        """Acquire `cost` tokens, blocking if necessary.

        Returns the time waited in seconds (0.0 if no wait).
        """
        waited = 0.0
        async with self._lock:
            self._refill()

            while self._tokens < cost:
                # Calculate how long we need to wait for enough tokens
                deficit = cost - self._tokens
                wait_time = deficit / self.refill_rate
                await asyncio.sleep(wait_time)
                waited += wait_time
                self._refill()

            self._tokens -= cost
            self.total_acquired += 1
            self.total_waited += waited

        return waited

    @property
    def available_tokens(self) -> float:
        """Current token count (approximate, no lock)."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        return min(self.capacity, self._tokens + elapsed * self.refill_rate)

    def __repr__(self) -> str:
        return (
            f"RateLimiter(capacity={self.capacity}, refill_rate={self.refill_rate}, "
            f"tokens={self.available_tokens:.1f}, acquired={self.total_acquired})"
        )
