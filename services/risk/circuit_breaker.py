"""Circuit Breaker — automated risk management safety guards.

Implements multiple layers of protection:
1. Max drawdown halt: Stop trading if unrealized P&L drops too far
2. Per-symbol exposure caps: Limit position size per asset
3. Total portfolio exposure cap: Limit total notional at risk
4. Daily loss limit: Hard stop for the day
5. Rapid loss detection: Halt if losses accumulate too quickly

Reference: "Building High-Performance Crypto Trading Bots: A Professional Developer's Guide"
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation — trading allowed
    OPEN = "open"           # Tripped — all trading halted
    HALF_OPEN = "half_open" # Recovery check — limited trading


@dataclass
class CircuitConfig:
    """Circuit breaker thresholds."""
    # Drawdown limits
    max_drawdown_pct: float = 5.0           # Max unrealized drawdown (% of equity)
    daily_loss_limit_pct: float = 3.0       # Max realized daily loss (% of starting equity)

    # Exposure limits
    max_per_symbol_notional: float = 50.0   # Max USD notional per symbol
    max_total_notional: float = 200.0       # Max total USD across all positions
    max_position_count: int = 10            # Max number of open positions

    # Rate limits
    max_orders_per_minute: int = 30         # Order rate limit
    max_consecutive_losses: int = 5         # Halt after N consecutive losing trades

    # Recovery
    cooldown_seconds: float = 300.0         # 5 minutes cooldown when tripped
    half_open_max_trades: int = 1           # Max trades in half-open state


@dataclass
class TripEvent:
    """Record of a circuit breaker trip."""
    reason: str
    severity: str  # "warning", "halt", "emergency"
    details: dict[str, Any]
    timestamp: float
    state_before: CircuitState
    state_after: CircuitState


class CircuitBreaker:
    """Multi-layer circuit breaker for trading risk management.

    Usage:
        breaker = CircuitBreaker(starting_equity=150.0)

        # Before any trade:
        if not breaker.can_trade("BTC-USD", notional=10.0):
            logger.warning("Circuit breaker: trading blocked")
            return

        # After each trade result:
        breaker.record_trade_result(pnl=-0.50, symbol="BTC-USD")

        # Periodic equity update:
        breaker.update_equity(current_equity=148.50)
    """

    def __init__(
        self,
        starting_equity: float = 150.0,
        config: CircuitConfig | None = None,
        on_trip: Optional[Callable[[TripEvent], None]] = None,
    ):
        self.config = config or CircuitConfig()
        self.starting_equity = starting_equity
        self.current_equity = starting_equity
        self.on_trip = on_trip

        self._state = CircuitState.CLOSED
        self._trip_time: float = 0.0
        self._trip_events: list[TripEvent] = []

        # Tracking
        self._daily_realized_pnl: float = 0.0
        self._consecutive_losses: int = 0
        self._order_timestamps: list[float] = []
        self._positions: dict[str, float] = {}  # symbol -> notional
        self._half_open_trades: int = 0
        self._peak_equity: float = starting_equity

    @property
    def state(self) -> CircuitState:
        """Current circuit breaker state."""
        # Check if cooldown has expired
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._trip_time
            if elapsed >= self.config.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_trades = 0
                logger.info("Circuit breaker: OPEN → HALF_OPEN (cooldown expired)")
        return self._state

    @property
    def is_trading_allowed(self) -> bool:
        """Whether any trading is currently allowed."""
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def can_trade(self, symbol: str, notional: float = 0.0) -> bool:
        """Check if a specific trade is allowed.

        Returns False if any circuit breaker condition would be violated.
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            return False

        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_trades >= self.config.half_open_max_trades:
                return False

        # Check per-symbol exposure
        current_symbol_notional = self._positions.get(symbol, 0.0)
        if current_symbol_notional + notional > self.config.max_per_symbol_notional:
            self._maybe_trip(
                f"Per-symbol exposure cap: {symbol} would be "
                f"${current_symbol_notional + notional:.2f} "
                f"(limit ${self.config.max_per_symbol_notional:.2f})",
                severity="warning",
            )
            return False

        # Check total exposure
        total_notional = sum(self._positions.values()) + notional
        if total_notional > self.config.max_total_notional:
            self._maybe_trip(
                f"Total exposure cap: ${total_notional:.2f} "
                f"(limit ${self.config.max_total_notional:.2f})",
                severity="warning",
            )
            return False

        # Check position count
        if (
            symbol not in self._positions
            and len(self._positions) >= self.config.max_position_count
        ):
            return False

        # Check order rate
        now = time.time()
        self._order_timestamps = [
            t for t in self._order_timestamps if now - t < 60
        ]
        if len(self._order_timestamps) >= self.config.max_orders_per_minute:
            return False

        return True

    def record_order(self) -> None:
        """Record that an order was placed (for rate limiting)."""
        self._order_timestamps.append(time.time())

    def record_trade_result(self, pnl: float, symbol: str = "") -> None:
        """Record a completed trade result."""
        self._daily_realized_pnl += pnl

        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_trades += 1
            if pnl >= 0:
                # Successful trade in half-open → close the breaker
                self._state = CircuitState.CLOSED
                logger.info("Circuit breaker: HALF_OPEN → CLOSED (successful trade)")

        # Check consecutive losses
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            self._trip(
                f"Consecutive losses: {self._consecutive_losses}",
                severity="halt",
                details={"consecutive_losses": self._consecutive_losses, "last_pnl": pnl},
            )

        # Check daily loss limit
        if self.starting_equity > 0 and self._daily_realized_pnl < 0:
            daily_loss_pct = abs(self._daily_realized_pnl) / self.starting_equity * 100
        else:
            daily_loss_pct = 0.0
        if self._daily_realized_pnl < 0 and daily_loss_pct >= self.config.daily_loss_limit_pct:
            self._trip(
                f"Daily loss limit: {daily_loss_pct:.1f}% "
                f"(limit {self.config.daily_loss_limit_pct:.1f}%)",
                severity="halt",
                details={
                    "daily_realized_pnl": self._daily_realized_pnl,
                    "daily_loss_pct": daily_loss_pct,
                },
            )

    def update_equity(self, current_equity: float) -> None:
        """Update current equity for drawdown monitoring."""
        self.current_equity = current_equity
        self._peak_equity = max(self._peak_equity, current_equity)

        # Check drawdown
        if self._peak_equity > 0:
            drawdown_pct = (self._peak_equity - current_equity) / self._peak_equity * 100
            if drawdown_pct >= self.config.max_drawdown_pct:
                self._trip(
                    f"Max drawdown: {drawdown_pct:.1f}% "
                    f"(limit {self.config.max_drawdown_pct:.1f}%)",
                    severity="emergency",
                    details={
                        "peak_equity": self._peak_equity,
                        "current_equity": current_equity,
                        "drawdown_pct": drawdown_pct,
                    },
                )

    def update_position(self, symbol: str, notional: float) -> None:
        """Update tracked position for a symbol."""
        if notional <= 0:
            self._positions.pop(symbol, None)
        else:
            self._positions[symbol] = notional

    def reset_daily(self, new_starting_equity: float | None = None) -> None:
        """Reset daily counters (call at start of each trading day)."""
        if new_starting_equity is not None:
            self.starting_equity = new_starting_equity
        self._daily_realized_pnl = 0.0
        self._consecutive_losses = 0
        self._peak_equity = self.current_equity
        if self._state != CircuitState.OPEN:
            self._state = CircuitState.CLOSED
        logger.info("Circuit breaker: daily reset (equity=$%.2f)", self.current_equity)

    def force_close(self) -> None:
        """Force the circuit breaker to CLOSED state."""
        self._state = CircuitState.CLOSED
        logger.info("Circuit breaker: forced CLOSED")

    def _trip(self, reason: str, severity: str = "halt", details: dict | None = None) -> None:
        """Trip the circuit breaker."""
        if self._state == CircuitState.OPEN:
            return  # Already tripped

        event = TripEvent(
            reason=reason,
            severity=severity,
            details=details or {},
            timestamp=time.time(),
            state_before=self._state,
            state_after=CircuitState.OPEN,
        )

        self._state = CircuitState.OPEN
        self._trip_time = time.time()
        self._trip_events.append(event)

        logger.warning("CIRCUIT BREAKER TRIPPED: %s [%s]", reason, severity)

        if self.on_trip:
            try:
                self.on_trip(event)
            except Exception as e:
                logger.error("Circuit breaker callback failed: %s", e)

    def _maybe_trip(self, reason: str, severity: str = "warning") -> None:
        """Log a warning but don't trip unless severity is halt+."""
        if severity in ("halt", "emergency"):
            self._trip(reason, severity)
        else:
            logger.warning("Circuit breaker warning: %s", reason)

    @property
    def summary(self) -> dict[str, Any]:
        """Current circuit breaker status summary."""
        return {
            "state": self.state.value,
            "starting_equity": self.starting_equity,
            "current_equity": self.current_equity,
            "peak_equity": self._peak_equity,
            "daily_realized_pnl": round(self._daily_realized_pnl, 2),
            "consecutive_losses": self._consecutive_losses,
            "positions": len(self._positions),
            "total_exposure": round(sum(self._positions.values()), 2),
            "orders_last_minute": len([
                t for t in self._order_timestamps if time.time() - t < 60
            ]),
            "trip_count": len(self._trip_events),
        }
