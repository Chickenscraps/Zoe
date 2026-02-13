"""
Token-bucket rate limiter for Robinhood Crypto API.

Enforces the sustained 100 RPM limit with priority tiers:
  CRITICAL  — order place/cancel: always served if tokens > 0
  NORMAL    — get_quote, get_order_status: standard queue
  LOW       — get_balance, get_holdings: skipped when tokens < 20

On 429 response from RH: call report_429() to pause and partially refill.

Usage:
    limiter = RateLimitManager(rpm=100)

    # Before any RH API call:
    if await limiter.acquire("CRITICAL"):
        response = await rh_client.place_order(...)
        if response.status == 429:
            await limiter.report_429()
    else:
        logger.warning("Rate limit: request denied (priority=LOW)")

References:
  [AA] §2.3 — 100 RPM sustained, burst up to 300 but don't rely on it
  [HL] §P0-5 — Rate-Limit Safety
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Priority tiers
CRITICAL = "CRITICAL"  # order place/cancel
NORMAL = "NORMAL"      # get_quote, get_order_status
LOW = "LOW"            # get_balance, get_holdings

# Minimum tokens required for LOW priority requests
LOW_PRIORITY_FLOOR = 20


@dataclass
class RateLimitStats:
    """Rolling stats for observability."""
    tokens_used: int = 0
    tokens_denied: int = 0
    http_429_count: int = 0
    window_start: float = field(default_factory=time.monotonic)

    def reset_if_stale(self, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        if now - self.window_start > window_seconds:
            self.tokens_used = 0
            self.tokens_denied = 0
            self.http_429_count = 0
            self.window_start = now


class RateLimitManager:
    """
    Async token-bucket rate limiter.

    Tokens refill continuously at `rpm / 60` per second.
    Burst capacity is capped at `burst` tokens.
    """

    def __init__(
        self,
        rpm: int = 100,
        burst: int = 150,
        backoff_seconds: float = 30.0,
    ):
        self.rpm = rpm
        self.burst = burst
        self.backoff_seconds = backoff_seconds

        self._tokens: float = float(burst)
        self._max_tokens: float = float(burst)
        self._refill_rate: float = rpm / 60.0  # tokens per second
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()
        self._paused_until: float = 0.0  # monotonic time when pause ends

        self.stats = RateLimitStats()

        logger.info(
            "RateLimitManager initialized: %d RPM, burst=%d, backoff=%.0fs",
            rpm, burst, backoff_seconds,
        )

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    async def acquire(
        self,
        priority: str = NORMAL,
        timeout: float = 10.0,
    ) -> bool:
        """
        Acquire a rate-limit token. Returns True if acquired, False if denied.

        CRITICAL: waits up to timeout for a token (never denied unless timeout)
        NORMAL:   waits up to timeout
        LOW:      immediately denied if tokens < LOW_PRIORITY_FLOOR
        """
        self.stats.reset_if_stale()

        async with self._lock:
            self._refill()

            # Check if we're in a 429 pause
            now = time.monotonic()
            if now < self._paused_until:
                wait_time = self._paused_until - now
                if priority == CRITICAL:
                    # Critical requests wait through the pause
                    logger.debug("CRITICAL request waiting %.1fs for 429 pause", wait_time)
                else:
                    self.stats.tokens_denied += 1
                    return False

        # LOW priority: deny immediately if bucket is low
        if priority == LOW:
            async with self._lock:
                self._refill()
                if self._tokens < LOW_PRIORITY_FLOOR:
                    self.stats.tokens_denied += 1
                    logger.debug(
                        "LOW priority denied (tokens=%.1f < %d)",
                        self._tokens, LOW_PRIORITY_FLOOR,
                    )
                    return False

        # Wait for a token with timeout
        deadline = time.monotonic() + timeout
        while True:
            async with self._lock:
                self._refill()

                # Wait through 429 pause
                now = time.monotonic()
                if now < self._paused_until:
                    if priority != CRITICAL:
                        self.stats.tokens_denied += 1
                        return False
                    # CRITICAL: keep waiting

                elif self._tokens >= 1.0:
                    self._tokens -= 1.0
                    self.stats.tokens_used += 1
                    return True

            # No token available — wait briefly then retry
            if time.monotonic() >= deadline:
                self.stats.tokens_denied += 1
                logger.warning(
                    "Rate limit timeout (priority=%s, tokens=%.1f)",
                    priority, self._tokens,
                )
                return False

            await asyncio.sleep(0.1)  # 100ms poll interval

    async def report_429(self) -> None:
        """
        Called when an RH API response returns HTTP 429.
        Pauses all requests for backoff_seconds and partially refills.
        """
        async with self._lock:
            self.stats.http_429_count += 1
            self._paused_until = time.monotonic() + self.backoff_seconds
            # Partial refill to 50% after pause
            self._tokens = self._max_tokens * 0.5
            logger.warning(
                "HTTP 429 received — pausing %.0fs, refilled to %.0f tokens",
                self.backoff_seconds, self._tokens,
            )

    @property
    def available_tokens(self) -> float:
        """Current token count (approximate, not locked)."""
        self._refill()
        return self._tokens

    def get_stats(self) -> dict:
        """Return stats for observability metrics."""
        self.stats.reset_if_stale()
        return {
            "tokens_available": round(self._tokens, 1),
            "tokens_used_1m": self.stats.tokens_used,
            "tokens_denied_1m": self.stats.tokens_denied,
            "http_429_count_1m": self.stats.http_429_count,
            "paused": time.monotonic() < self._paused_until,
        }
