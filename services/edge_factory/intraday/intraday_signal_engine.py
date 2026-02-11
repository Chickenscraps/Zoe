from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..config import EdgeFactoryConfig
from .regime_manager import IntradayRegime

logger = logging.getLogger(__name__)


@dataclass
class IntradaySignal:
    """Signal produced by the intraday engine."""

    symbol: str
    side: str = "buy"
    strategy: str = ""  # "sniper_mean_reversion" | "intraday_trend_follow"
    strength: float = 0.0
    expected_move_pct: float = 0.0
    tp_pct: float = 0.0
    sl_pct: float = 0.0
    time_stop_hours: int = 12
    regime: str = ""
    reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class IntradaySignalEngine:
    """
    Two intraday systems, gated by IntradayRegimeManager.

    A) SNIPER MEAN REVERSION (DEFENSIVE_SNIPER / RELIEF_RALLY):
       - Entry: RSI_4H < 28 (bear) or < 40 (bull) AND funding_rate_8h <= 0.001%
       - TP: +4.5%, SL: -3.0%, time stop: 12h

    B) INTRADAY TREND FOLLOW (TREND_FOLLOW only):
       - Entry: price > EMA50 AND RSI_4H recovering AND funding not danger
       - Trailing stop based on volatility
    """

    def __init__(self, config: EdgeFactoryConfig):
        self.config = config

    def evaluate(
        self,
        symbol: str,
        features: dict[str, float],
        regime: IntradayRegime,
    ) -> IntradaySignal | None:
        """
        Evaluate intraday signal for a symbol.

        Returns IntradaySignal or None if no entry.
        """
        if regime == IntradayRegime.OFF or regime == IntradayRegime.HALT:
            return None

        rsi_4h = features.get("rsi_4h", 50.0)
        funding = features.get("funding_rate_8h", 0.0)
        expected_move = features.get("expected_move_pct", 0.0)
        vwap_dist = features.get("vwap_distance", 0.0)

        if regime in (IntradayRegime.DEFENSIVE_SNIPER, IntradayRegime.RELIEF_RALLY):
            return self._sniper_signal(symbol, rsi_4h, funding, expected_move, regime)

        if regime == IntradayRegime.TREND_FOLLOW:
            return self._trend_follow_signal(
                symbol, rsi_4h, funding, expected_move, vwap_dist
            )

        return None

    def _sniper_signal(
        self,
        symbol: str,
        rsi_4h: float,
        funding: float,
        expected_move: float,
        regime: IntradayRegime,
    ) -> IntradaySignal | None:
        """Sniper mean reversion entry check."""
        # Check RSI threshold (depends on bear/bull context)
        if regime == IntradayRegime.DEFENSIVE_SNIPER:
            rsi_threshold = self.config.intraday_rsi_bear
        else:
            rsi_threshold = self.config.intraday_rsi_bull

        if rsi_4h >= rsi_threshold:
            return None  # RSI not oversold enough

        # Check funding is fearful (not overcrowded longs)
        if funding > self.config.intraday_funding_buy_max:
            return None  # Funding too high

        # Check expected move covers TP
        if expected_move > 0 and expected_move < self.config.intraday_tp_pct:
            return None  # Not enough expected movement

        # Compute signal strength from how oversold RSI is
        strength = min(1.0, (rsi_threshold - rsi_4h) / rsi_threshold)

        return IntradaySignal(
            symbol=symbol,
            side="buy",
            strategy="sniper_mean_reversion",
            strength=strength,
            expected_move_pct=expected_move,
            tp_pct=self.config.intraday_tp_pct,
            sl_pct=self.config.intraday_sl_pct,
            time_stop_hours=self.config.intraday_time_stop_hours,
            regime=regime.value,
            reason="RSI_4H=%.1f < %.1f, funding=%.5f" % (
                rsi_4h, rsi_threshold, funding,
            ),
        )

    def _trend_follow_signal(
        self,
        symbol: str,
        rsi_4h: float,
        funding: float,
        expected_move: float,
        vwap_dist: float,
    ) -> IntradaySignal | None:
        """Intraday trend follow entry check."""
        # Price must be above EMA50 (positive vwap distance)
        if vwap_dist <= 0:
            return None

        # RSI recovering (above 35) but not overbought (< 70)
        if rsi_4h < 35 or rsi_4h > 70:
            return None

        # Funding not danger (crowded longs)
        if funding > self.config.intraday_funding_danger:
            return None

        # Check expected move
        if expected_move > 0 and expected_move < self.config.intraday_tp_pct:
            return None

        strength = min(1.0, vwap_dist / 0.03)  # Scale by distance above VWAP

        return IntradaySignal(
            symbol=symbol,
            side="buy",
            strategy="intraday_trend_follow",
            strength=strength,
            expected_move_pct=expected_move,
            tp_pct=self.config.intraday_tp_pct,
            sl_pct=self.config.intraday_sl_pct,
            time_stop_hours=self.config.intraday_time_stop_hours,
            regime=IntradayRegime.TREND_FOLLOW.value,
            reason="trend: vwap_dist=%.3f%%, RSI=%.1f, funding=%.5f" % (
                vwap_dist * 100, rsi_4h, funding,
            ),
        )
