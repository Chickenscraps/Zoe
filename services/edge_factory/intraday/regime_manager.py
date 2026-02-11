from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..config import EdgeFactoryConfig

logger = logging.getLogger(__name__)


class IntradayRegime(str, Enum):
    """Intraday regime states."""

    OFF = "off"
    DEFENSIVE_SNIPER = "defensive_sniper"
    RELIEF_RALLY = "relief_rally"
    TREND_FOLLOW = "trend_follow"
    HALT = "halt"


@dataclass
class IntradayRegimeState:
    """Current intraday regime with metadata."""

    regime: IntradayRegime
    reason: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    features_used: dict[str, float] = field(default_factory=dict)


class IntradayRegimeManager:
    """
    Intraday regime state machine.

    States:
    - OFF (default): intraday disabled or conditions don't allow
    - DEFENSIVE_SNIPER: mean reversion only, RSI_4H < 28 required, max 2 bullets per dip
    - RELIEF_RALLY: intraday long-biased, funding negative >24h
    - TREND_FOLLOW: price > EMA50, reclaiming key level
    - HALT: spreads/volatility too high, event risk, or missing data

    Uses % bands from config, not hardcoded price levels (symbol-agnostic).
    """

    def __init__(self, config: EdgeFactoryConfig):
        self.config = config
        self._current = IntradayRegimeState(
            regime=IntradayRegime.OFF,
            reason="initial",
        )

    @property
    def current(self) -> IntradayRegimeState:
        return self._current

    def evaluate(
        self,
        features: dict[str, float],
        event_blocked: bool = False,
    ) -> IntradayRegimeState:
        """
        Evaluate intraday regime from features.

        Required feature keys:
        - current_price, ema50 (or vwap_distance as proxy)
        - range_24h_pct: (high-low)/open over 24h
        - rsi_4h: RSI on 4-hour bars
        - funding_rate_8h
        - liquidity_score: volume*close/abs(return)
        """
        if not self.config.intraday_enabled:
            self._current = IntradayRegimeState(
                regime=IntradayRegime.OFF,
                reason="intraday disabled",
            )
            return self._current

        range_24h = features.get("range_24h_pct", 0.0)
        liquidity = features.get("liquidity_score", 0.0)
        rsi_4h = features.get("rsi_4h", 50.0)
        funding = features.get("funding_rate_8h", 0.0)
        vwap_dist = features.get("vwap_distance", 0.0)
        spread_pct = features.get("spread_pct", 0.0)

        features_used = {
            "range_24h_pct": range_24h,
            "liquidity_score": liquidity,
            "rsi_4h": rsi_4h,
            "funding_rate_8h": funding,
            "vwap_distance": vwap_dist,
        }

        # HALT: volatility too high
        if range_24h > self.config.intraday_vol_halt_range:
            self._current = IntradayRegimeState(
                regime=IntradayRegime.HALT,
                reason="vol_halt: 24h range %.1f%% > %.1f%%" % (
                    range_24h * 100, self.config.intraday_vol_halt_range * 100,
                ),
                features_used=features_used,
            )
            logger.info("Intraday: HALT (vol %.1f%%)", range_24h * 100)
            return self._current

        # HALT: event risk window
        if event_blocked:
            self._current = IntradayRegimeState(
                regime=IntradayRegime.HALT,
                reason="event_risk_window",
                features_used=features_used,
            )
            logger.info("Intraday: HALT (event risk)")
            return self._current

        # HALT: spread too wide
        if spread_pct > self.config.max_spread_pct_entry:
            self._current = IntradayRegimeState(
                regime=IntradayRegime.HALT,
                reason="spread_halt: %.2f%% > max" % (spread_pct * 100),
                features_used=features_used,
            )
            return self._current

        # HALT: insufficient liquidity
        if liquidity > 0 and liquidity < self.config.intraday_liquidity_min:
            self._current = IntradayRegimeState(
                regime=IntradayRegime.HALT,
                reason="liquidity_halt: score %.0f < min %.0f" % (
                    liquidity, self.config.intraday_liquidity_min,
                ),
                features_used=features_used,
            )
            return self._current

        # TREND_FOLLOW: price above EMA50 (positive vwap distance as proxy)
        # AND funding not danger AND RSI recovering (> 35)
        if (vwap_dist > 0.01
                and funding < self.config.intraday_funding_danger
                and rsi_4h > 35):
            self._current = IntradayRegimeState(
                regime=IntradayRegime.TREND_FOLLOW,
                reason="price above EMA50, funding safe, RSI recovering",
                features_used=features_used,
            )
            logger.info("Intraday: TREND_FOLLOW")
            return self._current

        # RELIEF_RALLY: funding negative (shorts paying longs), price stabilizing
        if funding < 0 and rsi_4h < self.config.intraday_rsi_bull:
            self._current = IntradayRegimeState(
                regime=IntradayRegime.RELIEF_RALLY,
                reason="funding negative + RSI low",
                features_used=features_used,
            )
            logger.info("Intraday: RELIEF_RALLY")
            return self._current

        # DEFENSIVE_SNIPER: RSI deeply oversold
        if rsi_4h < self.config.intraday_rsi_bear:
            self._current = IntradayRegimeState(
                regime=IntradayRegime.DEFENSIVE_SNIPER,
                reason="RSI_4H %.1f < bear threshold %.1f" % (
                    rsi_4h, self.config.intraday_rsi_bear,
                ),
                features_used=features_used,
            )
            logger.info("Intraday: DEFENSIVE_SNIPER (RSI=%.1f)", rsi_4h)
            return self._current

        # Default: OFF (conditions don't warrant intraday)
        self._current = IntradayRegimeState(
            regime=IntradayRegime.OFF,
            reason="no intraday conditions met",
            features_used=features_used,
        )
        return self._current

    def allows_entries(self) -> bool:
        """True if current regime allows new intraday entries."""
        return self._current.regime in {
            IntradayRegime.DEFENSIVE_SNIPER,
            IntradayRegime.RELIEF_RALLY,
            IntradayRegime.TREND_FOLLOW,
        }
