"""
Phase 4 — Exit planning for bounce trades.

Implements four exit triggers:
  1. Standard TP   (+4.5% default, marketable limit at ask)
  2. Volatility SL  (ATR-based or hard -3%)
  3. Time stop     (12h default)
  4. Panic exit    (price < capitulation low → aggressive chase)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class ExitPlan:
    """Immutable exit parameters set at trade entry."""
    tp_price: float
    sl_price: float
    panic_price: float        # capitulation candle low
    time_stop_at: datetime
    entry_price: float
    entry_time: datetime


@dataclass
class ExitSignal:
    """Signal emitted when an exit condition fires."""
    trigger: str              # 'tp' | 'sl' | 'time_stop' | 'panic'
    target_price: float
    execution_mode: str       # 'marketable_limit' | 'aggressive_chase'
    reason: str = ""


def compute_exit_plan(
    entry_price: float,
    atr: float,
    cap_low: float,
    *,
    tp_pct: float = 0.045,
    sl_atr_mult: float = 1.5,
    sl_hard_pct: float = 0.03,
    time_stop_hours: int = 12,
    entry_time: Optional[datetime] = None,
) -> ExitPlan:
    """
    Build the exit plan at trade entry time.
    """
    if entry_time is None:
        entry_time = datetime.now(timezone.utc)

    tp_price = entry_price * (1.0 + tp_pct)

    sl_atr = entry_price - (sl_atr_mult * atr) if atr > 0 else entry_price * (1 - sl_hard_pct)
    sl_hard = entry_price * (1.0 - sl_hard_pct)
    sl_price = max(sl_atr, sl_hard)

    panic_price = cap_low if cap_low > 0 else sl_price

    time_stop_at = entry_time + timedelta(hours=time_stop_hours)

    return ExitPlan(
        tp_price=round(tp_price, 6),
        sl_price=round(sl_price, 6),
        panic_price=round(panic_price, 6),
        time_stop_at=time_stop_at,
        entry_price=entry_price,
        entry_time=entry_time,
    )


def check_exit(
    plan: ExitPlan,
    current_price: float,
    now: Optional[datetime] = None,
) -> Optional[ExitSignal]:
    """
    Evaluate current price + time against the exit plan.

    Returns ``None`` if no exit condition is met, otherwise the
    highest-priority exit signal.  Priority: panic > sl > tp > time.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Panic exit (highest priority — structural break)
    if current_price <= plan.panic_price:
        return ExitSignal(
            trigger="panic",
            target_price=current_price,
            execution_mode="aggressive_chase",
            reason=f"Price {current_price:.2f} <= panic threshold {plan.panic_price:.2f}",
        )

    # Stop loss
    if current_price <= plan.sl_price:
        return ExitSignal(
            trigger="sl",
            target_price=plan.sl_price,
            execution_mode="marketable_limit",
            reason=f"Price {current_price:.2f} <= SL {plan.sl_price:.2f}",
        )

    # Take profit
    if current_price >= plan.tp_price:
        return ExitSignal(
            trigger="tp",
            target_price=plan.tp_price,
            execution_mode="marketable_limit",
            reason=f"Price {current_price:.2f} >= TP {plan.tp_price:.2f}",
        )

    # Time stop
    if now >= plan.time_stop_at:
        return ExitSignal(
            trigger="time_stop",
            target_price=current_price,
            execution_mode="marketable_limit",
            reason=f"Time stop reached at {plan.time_stop_at.isoformat()}",
        )

    return None
