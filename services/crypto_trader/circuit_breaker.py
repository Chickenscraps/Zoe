"""Stale-data circuit breaker for the trading pipeline.

If market data for any focus symbol is older than a configurable threshold
(default: 5 seconds), the circuit breaker trips and blocks new order entries.
It automatically resets when fresh data arrives.

States:
  CLOSED  — data is fresh, trading allowed
  OPEN    — data is stale, trading blocked
"""

from __future__ import annotations

import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"  # healthy — trading allowed
    OPEN = "open"      # tripped — trading blocked


class CircuitBreaker:
    """Prevents order entry when market data is stale."""

    def __init__(self, threshold_s: float = 5.0):
        """
        Args:
            threshold_s: Max age (seconds) of focus data before tripping.
        """
        self.threshold_s = threshold_s
        self._state = CircuitState.CLOSED
        self._tripped_at: float = 0.0
        self._stale_symbols: list[str] = []

        # Stats
        self.trip_count: int = 0
        self.last_trip_duration_s: float = 0.0

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        """True if circuit is tripped (trading blocked)."""
        return self._state == CircuitState.OPEN

    @property
    def allows_trading(self) -> bool:
        """True if trading is allowed (circuit closed)."""
        return self._state == CircuitState.CLOSED

    @property
    def stale_symbols(self) -> list[str]:
        return list(self._stale_symbols)

    def check(self, market_data_service: 'MarketDataService') -> CircuitState:
        """Evaluate current data freshness and update state.

        Args:
            market_data_service: The MarketDataService to check for staleness.

        Returns:
            Current circuit state.
        """
        stale = market_data_service.stale_symbols(self.threshold_s)

        if stale:
            if self._state == CircuitState.CLOSED:
                # Trip the breaker
                self._state = CircuitState.OPEN
                self._tripped_at = time.time()
                self._stale_symbols = stale
                self.trip_count += 1
                logger.warning(
                    "Circuit breaker OPEN: %d stale focus symbols (threshold=%.1fs): %s",
                    len(stale), self.threshold_s, stale[:5],
                )
            else:
                self._stale_symbols = stale
        else:
            if self._state == CircuitState.OPEN:
                # Reset the breaker
                duration = time.time() - self._tripped_at
                self.last_trip_duration_s = duration
                self._state = CircuitState.CLOSED
                self._stale_symbols = []
                logger.info(
                    "Circuit breaker CLOSED: data is fresh (was open for %.1fs)", duration,
                )

        return self._state

    def force_close(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._stale_symbols = []

    def force_open(self, reason: str = "manual") -> None:
        """Manually trip the circuit breaker."""
        self._state = CircuitState.OPEN
        self._tripped_at = time.time()
        self._stale_symbols = [reason]
        self.trip_count += 1

    def status_dict(self) -> dict:
        """Return circuit breaker status as a dict for health reporting."""
        return {
            "state": self._state.value,
            "allows_trading": self.allows_trading,
            "threshold_s": self.threshold_s,
            "stale_symbols": self._stale_symbols,
            "trip_count": self.trip_count,
            "last_trip_duration_s": self.last_trip_duration_s,
        }
