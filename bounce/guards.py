"""
Guardrails — hard halt conditions that override the state machine.

Conditions that block new entries:
  1. Event risk window (FOMC, CPI, etc.)
  2. 24h volatility halt (range/open > threshold)
  3. Spread/liquidity halt (spread_pct > max)
  4. Weekend thin-liquidity dampener (optional)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def check_halt_conditions(
    symbol: str,
    market_state: Dict[str, Any],
    *,
    vol_halt_24h_range: float = 0.05,
    max_spread_pct: float = 0.003,
    weekend_dampener: bool = False,
    event_risk_windows: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """
    Check all guardrail conditions.

    Parameters
    ----------
    market_state : dict
        Expected keys (all optional — missing = not checked):
        - ``high_24h``, ``low_24h``, ``open_24h``: 24h OHLC for vol halt
        - ``best_bid``, ``best_ask``: for spread check
        - ``now``: datetime override (for testing)

    Returns
    -------
    list[str]
        Empty if all clear; otherwise list of halt reasons.
    """
    halts: List[str] = []

    # ── 1. Event risk ────────────────────────────────────────────────
    now = market_state.get("now", datetime.now(timezone.utc))
    if event_risk_windows:
        for window in event_risk_windows:
            start = window.get("start")
            end = window.get("end")
            if start and end and start <= now <= end:
                halts.append(f"event_risk: {window.get('label', 'unknown')}")

    # ── 2. 24h volatility halt ───────────────────────────────────────
    high_24h = _float(market_state, "high_24h")
    low_24h = _float(market_state, "low_24h")
    open_24h = _float(market_state, "open_24h")

    if high_24h > 0 and low_24h > 0 and open_24h > 0:
        range_ratio = (high_24h - low_24h) / open_24h
        if range_ratio > vol_halt_24h_range:
            halts.append(
                f"vol_halt: 24h range/open={range_ratio:.4f} > {vol_halt_24h_range}"
            )

    # ── 3. Spread / liquidity halt ───────────────────────────────────
    bid = _float(market_state, "best_bid")
    ask = _float(market_state, "best_ask")
    if bid > 0 and ask > 0:
        mid = (bid + ask) / 2.0
        spread_pct = (ask - bid) / mid if mid > 0 else 0
        if spread_pct > max_spread_pct:
            halts.append(
                f"spread_halt: spread_pct={spread_pct:.6f} > {max_spread_pct}"
            )

    # ── 4. Weekend dampener ──────────────────────────────────────────
    if weekend_dampener:
        weekday = now.weekday()
        if weekday >= 5:  # Saturday=5, Sunday=6
            halts.append("weekend_dampener: reduced confidence on weekends")

    if halts:
        logger.info("[%s] halt conditions: %s", symbol, halts)

    return halts


def _float(d: Dict[str, Any], key: str) -> float:
    try:
        return float(d.get(key, 0))
    except (ValueError, TypeError):
        return 0.0
