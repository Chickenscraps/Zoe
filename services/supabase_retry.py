"""
Supabase Retry Wrapper — shared exponential backoff for critical writes.

Modeled on FlushWorker's proven pattern (exponential backoff + jitter).
Use for any Supabase write in the trading hot path.

Usage:
    from services.supabase_retry import supabase_retry

    result = await supabase_retry(
        lambda: sb.table("crypto_fills").upsert(row).execute()
    )
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retry parameters (matching FlushWorker pattern)
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_JITTER = 0.5  # ±50% jitter


class SupabaseRetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"Supabase operation failed after {attempts} attempts: {last_error}"
        )


async def supabase_retry(
    operation: Callable[[], Any],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    jitter: float = DEFAULT_JITTER,
    operation_name: str = "supabase_write",
) -> Any:
    """Execute a Supabase operation with exponential backoff retry.

    Args:
        operation: Callable that performs the Supabase operation (sync or async).
        max_attempts: Maximum number of attempts before giving up.
        initial_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        backoff_factor: Multiplier applied to delay after each failure.
        jitter: Random jitter factor (±jitter * delay).
        operation_name: Human-readable name for logging.

    Returns:
        The result of the Supabase operation.

    Raises:
        SupabaseRetryExhausted: When all attempts are exhausted.
    """
    delay = initial_delay
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = operation()
            # Handle async operations
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                result = await result
            return result

        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            # Don't retry on 409 Conflict (idempotent upsert already succeeded)
            if "409" in str(e) or "conflict" in error_str or "duplicate" in error_str:
                logger.debug(
                    "%s: conflict/duplicate (idempotent success): %s",
                    operation_name,
                    e,
                )
                return None  # Treat as success

            # Don't retry on 400 Bad Request (schema/validation error)
            if "400" in str(e) and "bad request" in error_str:
                logger.error(
                    "%s: bad request (not retryable): %s", operation_name, e
                )
                raise

            if attempt < max_attempts:
                # Add jitter: delay ± (jitter * delay)
                jittered = delay * (1 + random.uniform(-jitter, jitter))
                logger.warning(
                    "%s: attempt %d/%d failed, retrying in %.1fs: %s",
                    operation_name,
                    attempt,
                    max_attempts,
                    jittered,
                    e,
                )
                await asyncio.sleep(jittered)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(
                    "%s: all %d attempts exhausted: %s",
                    operation_name,
                    max_attempts,
                    e,
                )

    raise SupabaseRetryExhausted(max_attempts, last_error)  # type: ignore[arg-type]


def supabase_retry_sync(
    operation: Callable[[], Any],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    operation_name: str = "supabase_write",
) -> Any:
    """Synchronous version for non-async contexts.

    Uses exponential backoff matching the async version.
    Use sparingly — prefer the async version.
    """
    import time

    delay = initial_delay
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "409" in str(e) or "conflict" in error_str or "duplicate" in error_str:
                return None
            if "400" in str(e) and "bad request" in error_str:
                raise
            if attempt < max_attempts:
                logger.warning(
                    "%s: sync attempt %d/%d failed, retrying in %.1fs: %s",
                    operation_name,
                    attempt,
                    max_attempts,
                    delay,
                    e,
                )
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
    raise SupabaseRetryExhausted(max_attempts, last_error)  # type: ignore[arg-type]
