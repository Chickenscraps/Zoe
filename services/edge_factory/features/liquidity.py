from __future__ import annotations

import math
from typing import Any

from ..models import FeatureSnapshot
from .base import BaseFeature


class AmihudIlliquidity(BaseFeature):
    """
    Amihud Illiquidity Ratio (30-day moving average).

    Formula: |daily_return| / daily_dollar_volume
    Averaged over last 30 days of OHLCV data.

    High Amihud = illiquid market = dangerous to trade.
    Low Amihud = liquid market = safe to trade.

    Source: polygon (uses bars_daily from MarketDataIngestor)
    """

    name = "amihud_illiquidity"
    source = "polygon"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) < 10:
            return None

        window = bars[-30:]
        ratios = []

        for i in range(1, len(window)):
            c = window[i].get("close", 0)
            c_prev = window[i - 1].get("close", 0)
            v = window[i].get("volume", 0)

            if c <= 0 or c_prev <= 0 or v <= 0:
                continue

            daily_return = abs((c - c_prev) / c_prev)
            dollar_volume = c * v

            if dollar_volume > 0:
                ratios.append(daily_return / dollar_volume)

        if len(ratios) < 5:
            return None

        return sum(ratios) / len(ratios)


class AmihudSpikeDetector(BaseFeature):
    """
    Z-score of current Amihud vs 30-day history.

    spike_z > 2.0 = liquidity hole -> triggers crash regime.

    Uses feature history to compute z-score of the most recent
    Amihud value against its own rolling window.
    """

    name = "amihud_spike_z"
    source = "polygon"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) < 15:
            return None

        # Compute recent Amihud values (daily)
        window = bars[-31:]
        ratios = []

        for i in range(1, len(window)):
            c = window[i].get("close", 0)
            c_prev = window[i - 1].get("close", 0)
            v = window[i].get("volume", 0)

            if c <= 0 or c_prev <= 0 or v <= 0:
                continue

            daily_return = abs((c - c_prev) / c_prev)
            dollar_volume = c * v

            if dollar_volume > 0:
                ratios.append(daily_return / dollar_volume)

        if len(ratios) < 10:
            return None

        # Current = last ratio, history = all but last
        current = ratios[-1]
        hist_ratios = ratios[:-1]

        mean = sum(hist_ratios) / len(hist_ratios)
        variance = sum((r - mean) ** 2 for r in hist_ratios) / len(hist_ratios)
        std = math.sqrt(variance) if variance > 0 else 0

        if std <= 0:
            return 0.0

        z_score = (current - mean) / std
        return z_score
