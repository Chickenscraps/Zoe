from __future__ import annotations

import math
from typing import Any

from ..models import FeatureSnapshot
from .base import BaseFeature


class TrendZScore14D(BaseFeature):
    """
    Google Trends Z-Score over a 14-day rolling window.

    Z = (current_interest - mean_14d) / std_14d

    Interpretation:
    - Z > 0.8: Attention spike — retail FOMO building (bullish entry signal)
    - Z > 2.0: Extreme hype — likely blow-off top approaching
    - Z < -1.0: Interest collapse — potential bottom
    """

    name = "trend_z_score_14d"
    source = "google_trends"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        series = raw_data.get("interest_over_time", [])
        if not series or len(series) < 7:
            return None

        # Use up to 14 data points
        window = series[-14:] if len(series) >= 14 else series
        n = len(window)
        mean = sum(window) / n
        variance = sum((x - mean) ** 2 for x in window) / n
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std < 0.01:
            return 0.0

        current = series[-1]
        return (current - mean) / std


class TrendMomentum3D(BaseFeature):
    """
    3-day momentum of Google Trends interest.

    momentum = (interest_today - interest_3d_ago) / max(interest_3d_ago, 1)

    Measures the acceleration of retail attention.
    Positive = growing interest. Negative = waning interest.
    """

    name = "trend_momentum_3d"
    source = "google_trends"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        series = raw_data.get("interest_over_time", [])
        if not series or len(series) < 4:
            return None

        current = series[-1]
        three_days_ago = series[-4]
        base = max(three_days_ago, 1.0)
        return (current - three_days_ago) / base
