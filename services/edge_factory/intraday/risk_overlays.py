from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..config import EdgeFactoryConfig
from ..repository import FeatureRepository
from .regime_manager import IntradayRegime

logger = logging.getLogger(__name__)


class RiskOverlays:
    """
    Additional risk checks beyond the existing sizing module.

    - Max bullets per dip: max 2 entries within 24h per symbol in DEFENSIVE_SNIPER
    - Volatility HALT: if 24h range > 5%, block entries (exits allowed)
    - Liquidity HALT: if liquidity proxy < threshold, block entries

    Exits are always allowed regardless of overlays.
    """

    def __init__(self, config: EdgeFactoryConfig, repository: FeatureRepository):
        self.config = config
        self.repo = repository

    def check_all(
        self,
        symbol: str,
        regime: IntradayRegime,
        features: dict[str, float],
    ) -> tuple[bool, str]:
        """
        Run all risk overlays.

        Returns (allowed: bool, reason: str).
        """
        # Check bullets per dip
        allowed, reason = self._check_bullets(symbol, regime)
        if not allowed:
            return False, reason

        # Check volatility halt
        allowed, reason = self._check_vol_halt(features)
        if not allowed:
            return False, reason

        # Check liquidity halt
        allowed, reason = self._check_liquidity_halt(features)
        if not allowed:
            return False, reason

        return True, ""

    def _check_bullets(self, symbol: str, regime: IntradayRegime) -> tuple[bool, str]:
        """Max entries within 24h per symbol in DEFENSIVE_SNIPER."""
        if regime != IntradayRegime.DEFENSIVE_SNIPER:
            return True, ""

        max_bullets = self.config.intraday_max_bullets_24h
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        # Count open + recently closed positions for this symbol
        open_pos = self.repo.get_open_positions()
        open_count = sum(1 for p in open_pos if p.symbol == symbol)

        closed = self.repo.get_closed_positions(limit=50)
        recent_closed = sum(
            1 for p in closed
            if p.symbol == symbol and (p.entry_time or now) > cutoff
        )

        total = open_count + recent_closed
        if total >= max_bullets:
            return False, "bullets: %d/%d entries for %s in 24h" % (
                total, max_bullets, symbol,
            )

        return True, ""

    def _check_vol_halt(self, features: dict[str, float]) -> tuple[bool, str]:
        """Block entries if 24h range exceeds threshold."""
        range_24h = features.get("range_24h_pct", 0.0)
        if range_24h > self.config.intraday_vol_halt_range:
            return False, "vol_halt: 24h range %.1f%% > %.1f%%" % (
                range_24h * 100, self.config.intraday_vol_halt_range * 100,
            )
        return True, ""

    def _check_liquidity_halt(self, features: dict[str, float]) -> tuple[bool, str]:
        """Block entries if liquidity is below minimum."""
        liquidity = features.get("liquidity_score", 0.0)
        if liquidity > 0 and liquidity < self.config.intraday_liquidity_min:
            return False, "liquidity_halt: score %.0f < min %.0f" % (
                liquidity, self.config.intraday_liquidity_min,
            )
        return True, ""
