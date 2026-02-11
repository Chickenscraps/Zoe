"""
Phase 2 — Stabilization confirmation (2-of-4 multi-factor).

Requires at least ``confirmations_required`` of 4 non-correlated signals:
  1. Higher Lows  — last K candle lows form an ascending floor
  2. Micro-Breakout — close > capitulation candle high (or local swing)
  3. RSI Reclaim  — RSI crosses above 30 from oversold
  4. Funding Support — neutral/negative funding rate
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd


def check_stabilization(
    df_15m: pd.DataFrame,
    cap_candle: pd.Series | Dict[str, Any],
    indicators: Dict[str, Any],
    *,
    confirmations_required: int = 2,
    higher_lows_k: int = 4,
    rsi_reclaim: float = 30.0,
    funding_support_max_8h: float = 0.001,
    allow_missing_altdata: bool = True,
) -> Tuple[bool, List[str]]:
    """
    Evaluate stabilization signals after a capitulation event.

    Parameters
    ----------
    df_15m : DataFrame
        Recent 15-minute OHLCV candles (newest last).
    cap_candle : Series | dict
        The capitulation candle (needs 'high', 'low' at minimum).
    indicators : dict
        External indicator values, e.g. ``{"rsi_15m": 28, "funding_8h": -0.0002}``.

    Returns
    -------
    (is_stabilized, confirmations)
        ``confirmations`` lists which signals fired (e.g. ``["higher_lows", "rsi_reclaim"]``).
    """
    confirms: List[str] = []

    # ── 1. Higher lows ───────────────────────────────────────────────
    if len(df_15m) >= higher_lows_k:
        last_k = df_15m.tail(higher_lows_k)
        lows = last_k["low"].values.astype(float)
        if all(lows[i] >= lows[i - 1] for i in range(1, len(lows))):
            confirms.append("higher_lows")

    # ── 2. Micro-breakout ────────────────────────────────────────────
    cap_high = _safe_float(cap_candle, "high")
    if len(df_15m) >= 1 and cap_high > 0:
        current_close = float(df_15m.iloc[-1]["close"])
        if current_close > cap_high:
            confirms.append("micro_breakout")

    # ── 3. RSI reclaim ───────────────────────────────────────────────
    rsi = indicators.get("rsi_15m")
    if rsi is not None:
        try:
            rsi_val = float(rsi)
            if rsi_val > rsi_reclaim:
                confirms.append("rsi_reclaim")
        except (ValueError, TypeError):
            pass

    # ── 4. Funding support ───────────────────────────────────────────
    funding = indicators.get("funding_8h")
    if funding is not None:
        try:
            funding_val = float(funding)
            if funding_val <= funding_support_max_8h:
                confirms.append("funding_supportive")
        except (ValueError, TypeError):
            pass
    elif not allow_missing_altdata:
        # Strict mode: missing funding counts against
        pass
    # else: missing data is neutral — don't penalise, don't credit

    is_stabilized = len(confirms) >= confirmations_required
    return is_stabilized, confirms


def _safe_float(obj: Any, key: str) -> float:
    """Extract a float from a Series or dict, defaulting to 0."""
    try:
        if isinstance(obj, dict):
            return float(obj.get(key, 0))
        return float(obj[key])
    except (KeyError, TypeError, ValueError):
        return 0.0
