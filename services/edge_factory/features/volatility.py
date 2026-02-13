from __future__ import annotations

import logging
import math
from typing import Any

from ..models import FeatureSnapshot
from .base import BaseFeature

logger = logging.getLogger(__name__)


class ExpectedMovePct(BaseFeature):
    """
    Expected move percentage over 48 hours.

    Converts Garman-Klass daily volatility to a 48-hour expected move:
        expected_move = daily_vol * sqrt(2)

    Used by churn control: don't enter if expected_move < TP target.
    Clamped to [0.3%, 15%] to handle edge cases.

    Source: polygon (uses bars_daily for GK vol computation)

    Fallback: if bars_daily is empty/stale (Polygon rate-limited), reuses
    the last successfully computed value from feature history so that
    TradeIntentBuilder isn't permanently blocked.
    """

    name = "expected_move_pct"
    source = "polygon"

    # Clamp bounds
    MIN_MOVE = 0.003   # 0.3%
    MAX_MOVE = 0.15    # 15%

    # Conservative default for crypto when Polygon is completely unavailable.
    # 4% 48h expected move is typical for BTC/ETH in normal conditions.
    # This allows trading while being conservative on position sizing.
    DEFAULT_MOVE = 0.04  # 4%

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) >= 10:
            result = self._compute_from_bars(bars)
            if result is not None:
                return result

        # Bars insufficient — fall back to last known good value from history
        if history:
            last = history[0]  # most recent snapshot
            if last.value is not None and last.value > 0:
                logger.debug(
                    "expected_move_pct: using cached value %.4f (bars=%d, stale Polygon data)",
                    last.value, len(bars),
                )
                return last.value

        # No bars AND no history — use conservative default so trading isn't
        # permanently blocked by Polygon rate limits / outages
        logger.info(
            "expected_move_pct: no bars (%d) and no history, using default %.1f%%",
            len(bars), self.DEFAULT_MOVE * 100,
        )
        return self.DEFAULT_MOVE

    def _compute_from_bars(self, bars: list[dict]) -> float | None:
        """Compute GK volatility from daily OHLCV bars."""
        window = bars[-30:]
        gk_sum = 0.0
        count = 0

        for bar in window:
            o = bar.get("open", 0)
            h = bar.get("high", 0)
            l = bar.get("low", 0)
            c = bar.get("close", 0)

            if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                continue

            hl = math.log(h / l)
            co = math.log(c / o)
            gk_sum += 0.5 * hl ** 2 - (2 * math.log(2) - 1) * co ** 2
            count += 1

        if count < 5:
            return None

        daily_var = gk_sum / count
        daily_vol = math.sqrt(max(daily_var, 0))

        # 48-hour expected move = daily_vol * sqrt(2)
        expected_move = daily_vol * math.sqrt(2)

        # Clamp
        return max(self.MIN_MOVE, min(expected_move, self.MAX_MOVE))
