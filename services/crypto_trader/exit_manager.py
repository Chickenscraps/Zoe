"""SmartExitManager — stateful exit engine for open positions.

Implements a 7-tier exit hierarchy (highest priority first):
    1. Panic Stop    — price below catastrophic threshold (-5%)
    2. Hard Stop     — price below stop-loss (-3%)
    3. Spread Blowout — spread > 1.0% while holding
    4. Thesis Invalid — consensus dropped below 3/7 gates
    5. Trailing Stop  — price fell from high-water mark (-1.5% or 1xATR)
    6. Take Profit    — price above target (+4.5%)
    7. Time Stop      — position held too long (12h bounce, 48h trend)

Each check runs every tick (60s). The manager is stateful: it tracks
high-water marks, entry times, and exit reasons per position.

Usage:
    exit_mgr = SmartExitManager(price_cache, consensus_engine)
    for symbol, qty, entry_price, entry_time in open_positions:
        result = exit_mgr.check_exits(symbol, qty, entry_price, entry_time)
        if result is not None:
            # result.reason, result.target_price, result.urgency
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .price_cache import PriceCache
    from .consensus import ConsensusEngine


class ExitReason(Enum):
    PANIC_STOP = "panic_stop"
    HARD_STOP = "hard_stop"
    SPREAD_BLOWOUT = "spread_blowout"
    THESIS_INVALID = "thesis_invalid"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    TIME_STOP = "time_stop"
    MANUAL = "manual"
    KILL_SWITCH = "kill_switch"


class ExitUrgency(Enum):
    """How aggressively to exit."""
    MARKET = "market"       # panic — take whatever price
    AGGRESSIVE = "aggressive"  # cross spread, limit at ask
    NORMAL = "normal"       # limit at mid
    PASSIVE = "passive"     # limit at bid, wait for fill


@dataclass
class ExitSignal:
    """Emitted when an exit condition is met."""
    symbol: str
    reason: ExitReason
    target_price: float
    urgency: ExitUrgency
    pnl_pct: float  # unrealized P&L at exit decision
    details: str     # human-readable explanation

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "reason": self.reason.value,
            "target_price": self.target_price,
            "urgency": self.urgency.value,
            "pnl_pct": round(self.pnl_pct, 4),
            "details": self.details,
        }


@dataclass
class PositionState:
    """Tracked state for each open position."""
    symbol: str
    entry_price: float
    entry_time: datetime
    high_water_mark: float  # highest price since entry
    trailing_active: bool = False
    last_consensus_gates: int = 7

    def update_hwm(self, current_price: float) -> None:
        if current_price > self.high_water_mark:
            self.high_water_mark = current_price


# ── Configuration ────────────────────────────────────────────

@dataclass
class ExitConfig:
    """All exit thresholds in one place."""
    # Panic stop: catastrophic move
    panic_stop_pct: float = 0.05          # -5% from entry

    # Hard stop: risk limit
    hard_stop_pct: float = 0.03           # -3% from entry

    # Spread blowout: liquidity dried up
    spread_blowout_pct: float = 0.01      # 1.0% spread

    # Thesis invalidation: consensus dropped
    min_consensus_gates: int = 3           # if gates < this, exit

    # Trailing stop: profit protection
    trailing_activate_pct: float = 0.015   # activate after +1.5%
    trailing_distance_pct: float = 0.015   # trail by 1.5%

    # Take profit
    take_profit_pct: float = 0.045         # +4.5% from entry

    # Time stop
    time_stop_bounce_hours: float = 12.0   # bounce trades
    time_stop_trend_hours: float = 48.0    # trend trades
    default_time_stop_hours: float = 24.0  # fallback


class SmartExitManager:
    """Stateful exit manager that checks all exit conditions per tick."""

    def __init__(
        self,
        price_cache: PriceCache,
        consensus_engine: ConsensusEngine | None = None,
        config: ExitConfig | None = None,
    ):
        self.price_cache = price_cache
        self.consensus = consensus_engine
        self.cfg = config or ExitConfig()
        self._positions: dict[str, PositionState] = {}

    def register_position(
        self,
        symbol: str,
        entry_price: float,
        entry_time: datetime,
    ) -> None:
        """Register a new position for exit monitoring."""
        self._positions[symbol] = PositionState(
            symbol=symbol,
            entry_price=entry_price,
            entry_time=entry_time,
            high_water_mark=entry_price,
        )

    def unregister_position(self, symbol: str) -> None:
        """Remove a position from monitoring (already exited)."""
        self._positions.pop(symbol, None)

    def check_exits(
        self,
        symbol: str,
        current_price: float,
        current_spread_pct: float = 0.0,
        strategy: str = "",
    ) -> ExitSignal | None:
        """Check all exit conditions for a position. Returns ExitSignal or None.

        Priority order matters — first match wins.
        """
        state = self._positions.get(symbol)
        if state is None:
            return None

        # Update high-water mark
        state.update_hwm(current_price)

        entry = state.entry_price
        if entry <= 0:
            return None

        pnl_pct = (current_price - entry) / entry
        now = datetime.now(timezone.utc)
        holding_hours = (now - state.entry_time).total_seconds() / 3600

        # ── Priority 1: Panic Stop ──
        if pnl_pct <= -self.cfg.panic_stop_pct:
            return ExitSignal(
                symbol=symbol,
                reason=ExitReason.PANIC_STOP,
                target_price=current_price,
                urgency=ExitUrgency.MARKET,
                pnl_pct=pnl_pct,
                details=f"PANIC: {pnl_pct:.2%} loss exceeds -{self.cfg.panic_stop_pct:.1%} threshold",
            )

        # ── Priority 2: Hard Stop ──
        if pnl_pct <= -self.cfg.hard_stop_pct:
            return ExitSignal(
                symbol=symbol,
                reason=ExitReason.HARD_STOP,
                target_price=entry * (1 - self.cfg.hard_stop_pct),
                urgency=ExitUrgency.AGGRESSIVE,
                pnl_pct=pnl_pct,
                details=f"STOP: {pnl_pct:.2%} loss hit -{self.cfg.hard_stop_pct:.1%} stop",
            )

        # ── Priority 3: Spread Blowout ──
        if current_spread_pct > self.cfg.spread_blowout_pct:
            return ExitSignal(
                symbol=symbol,
                reason=ExitReason.SPREAD_BLOWOUT,
                target_price=current_price,
                urgency=ExitUrgency.NORMAL,
                pnl_pct=pnl_pct,
                details=f"SPREAD BLOWOUT: {current_spread_pct:.3%} > {self.cfg.spread_blowout_pct:.1%} limit",
            )

        # ── Priority 4: Thesis Invalidation (consensus check) ──
        if self.consensus is not None:
            snap = self.price_cache.snapshot(symbol)
            report = self.consensus.evaluate(snap, direction="long")
            state.last_consensus_gates = report.gates_passed

            if report.gates_passed < self.cfg.min_consensus_gates:
                return ExitSignal(
                    symbol=symbol,
                    reason=ExitReason.THESIS_INVALID,
                    target_price=current_price,
                    urgency=ExitUrgency.NORMAL,
                    pnl_pct=pnl_pct,
                    details=f"THESIS INVALID: consensus {report.gates_passed}/{report.gates_total} < {self.cfg.min_consensus_gates} min",
                )

        # ── Priority 5: Trailing Stop ──
        if pnl_pct >= self.cfg.trailing_activate_pct:
            state.trailing_active = True

        if state.trailing_active:
            hwm = state.high_water_mark
            trail_trigger = hwm * (1 - self.cfg.trailing_distance_pct)
            if current_price <= trail_trigger:
                hwm_pnl = (hwm - entry) / entry
                return ExitSignal(
                    symbol=symbol,
                    reason=ExitReason.TRAILING_STOP,
                    target_price=trail_trigger,
                    urgency=ExitUrgency.AGGRESSIVE,
                    pnl_pct=pnl_pct,
                    details=f"TRAILING: price {current_price:.2f} fell below trail {trail_trigger:.2f} (HWM was {hwm:.2f}, +{hwm_pnl:.2%})",
                )

        # ── Priority 6: Take Profit ──
        if pnl_pct >= self.cfg.take_profit_pct:
            return ExitSignal(
                symbol=symbol,
                reason=ExitReason.TAKE_PROFIT,
                target_price=entry * (1 + self.cfg.take_profit_pct),
                urgency=ExitUrgency.PASSIVE,
                pnl_pct=pnl_pct,
                details=f"TAKE PROFIT: {pnl_pct:.2%} >= +{self.cfg.take_profit_pct:.1%} target",
            )

        # ── Priority 7: Time Stop ──
        if "bounce" in strategy or "mean_reversion" in strategy:
            max_hours = self.cfg.time_stop_bounce_hours
        elif "trend" in strategy:
            max_hours = self.cfg.time_stop_trend_hours
        else:
            max_hours = self.cfg.default_time_stop_hours

        if holding_hours >= max_hours:
            return ExitSignal(
                symbol=symbol,
                reason=ExitReason.TIME_STOP,
                target_price=current_price,
                urgency=ExitUrgency.NORMAL,
                pnl_pct=pnl_pct,
                details=f"TIME STOP: held {holding_hours:.1f}h >= {max_hours:.0f}h limit",
            )

        return None

    def get_position_state(self, symbol: str) -> PositionState | None:
        return self._positions.get(symbol)

    def active_positions(self) -> list[str]:
        return list(self._positions.keys())
