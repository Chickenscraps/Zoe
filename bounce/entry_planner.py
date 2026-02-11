"""
Phase 3 — Entry planning.

Builds a ``TradeIntent`` that the execution engine (existing order manager)
can consume.  Uses limit-first "marketable limit" semantics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class TradeIntent:
    """
    A structured intent to enter a bounce trade.

    The execution engine decides whether to actually place the order
    based on sizing gates, churn limits, and account state.
    """
    symbol: str
    side: str = "buy"
    entry_style: str = "retest"          # 'retest' | 'breakout'
    entry_price: float = 0.0
    expected_move_pct: float = 0.0
    tp_price: float = 0.0
    sl_price: float = 0.0
    time_stop_hours: int = 12
    score: int = 0
    components: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_style": self.entry_style,
            "entry_price": self.entry_price,
            "expected_move_pct": self.expected_move_pct,
            "tp_price": self.tp_price,
            "sl_price": self.sl_price,
            "time_stop_hours": self.time_stop_hours,
            "score": self.score,
            "components": self.components,
            "reason": self.reason,
            "created_at": self.created_at,
        }


def build_trade_intent(
    symbol: str,
    cap_metrics: Dict[str, Any],
    score_data: Dict[str, Any],
    current_price: float,
    atr: float,
    *,
    tp_pct: float = 0.045,
    sl_atr_mult: float = 1.5,
    sl_hard_pct: float = 0.03,
    time_stop_hours: int = 12,
    entry_style: str = "retest",
    cap_low: float = 0.0,
) -> TradeIntent:
    """
    Build a TradeIntent from capitulation metrics and scoring.

    Parameters
    ----------
    cap_metrics : dict
        From ``detect_capitulation_event``.
    score_data : dict
        From ``calculate_bounce_score``.
    current_price : float
        Current bid/mid price.
    atr : float
        Current ATR for stop computation.
    cap_low : float
        The capitulation candle's low — panic exit threshold.
    """
    # Expected move: conservative proxy = ATR / price
    expected_move_pct = (atr / current_price) if current_price > 0 else 0
    # Also consider Garman-Klass proxy from cap candle data
    gk_move = _garman_klass_move(cap_metrics)
    expected_move_pct = max(expected_move_pct, gk_move)

    # Entry price: current price (marketable limit)
    entry_price = current_price

    # Take profit
    tp_price = entry_price * (1.0 + tp_pct)

    # Stop loss: wider of ATR-based and hard-pct (for tiny accounts)
    sl_atr = entry_price - (sl_atr_mult * atr) if atr > 0 else entry_price * (1 - sl_hard_pct)
    sl_hard = entry_price * (1.0 - sl_hard_pct)
    sl_price = max(sl_atr, sl_hard)  # tighter of the two

    # But never set SL above capitulation low (that's the panic threshold)
    if cap_low > 0 and sl_price < cap_low:
        sl_price = cap_low

    return TradeIntent(
        symbol=symbol,
        side="buy",
        entry_style=entry_style,
        entry_price=round(entry_price, 6),
        expected_move_pct=round(expected_move_pct, 6),
        tp_price=round(tp_price, 6),
        sl_price=round(sl_price, 6),
        time_stop_hours=time_stop_hours,
        score=score_data.get("score", 0),
        components=score_data.get("components", {}),
        reason=f"Bounce entry: score={score_data.get('score', 0)}, style={entry_style}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _garman_klass_move(cap_metrics: Dict[str, Any]) -> float:
    """
    Garman-Klass volatility estimator from a single OHLC candle.

    Returns an approximate expected move as a fraction (not percent).
    """
    tr = float(cap_metrics.get("tr", 0))
    atr = float(cap_metrics.get("atr", 1))
    if atr <= 0:
        return 0.0
    # Simplified: use normalised TR as a volatility proxy
    return min(tr / atr * 0.01, 0.10)  # cap at 10%
