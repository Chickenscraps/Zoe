from __future__ import annotations

import math
from typing import Any

from ..models import FeatureSnapshot
from .base import BaseFeature


class ExpectedMovePct(BaseFeature):
    """
    Expected move percentage over 48 hours.

    Converts Garman-Klass daily volatility to a 48-hour expected move:
        expected_move = daily_vol * sqrt(2)

    Used by churn control: don't enter if expected_move < TP target.
    Clamped to [0.3%, 15%] to handle edge cases.

    Source: polygon (uses bars_daily for GK vol computation)
    """

    name = "expected_move_pct"
    source = "polygon"

    # Clamp bounds
    MIN_MOVE = 0.003   # 0.3%
    MAX_MOVE = 0.15    # 15%

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) < 10:
            return None

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
