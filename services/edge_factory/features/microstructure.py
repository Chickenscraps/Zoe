from __future__ import annotations

import math
from typing import Any

from ..models import FeatureSnapshot
from .base import BaseFeature


class FundingRateBasis(BaseFeature):
    """
    Perpetual futures funding rate from OKX.

    Raw 8-hour rate, e.g. 0.0001 = 0.01%.

    Interpretation:
    - rate < 0.05% (0.0005): Market not overheated — safe to enter long.
    - rate > 0.05%: Overcrowded long positioning — leverage flush risk.
    - rate < 0 (negative): Short squeeze potential — strong long signal.
    """

    name = "funding_rate_basis"
    source = "okx"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        rate = raw_data.get("funding_rate")
        if rate is None:
            return None
        return float(rate)


class CorwinSchultzSpread(BaseFeature):
    """
    Corwin-Schultz bid-ask spread estimator from OHLC data.

    Uses high-low price variance to estimate the effective spread
    without needing Level 2 order book data.

    Formula (simplified):
        beta_j = [ln(H_j/L_j)]^2  for each day j
        beta = mean(beta_j + beta_{j-1}) over rolling window
        gamma = [ln(H_max(j,j-1) / L_min(j,j-1))]^2
        alpha = (sqrt(2*beta) - sqrt(beta)) / (3 - 2*sqrt(2)) - sqrt(gamma/(3-2*sqrt(2)))
        spread = 2 * (exp(alpha) - 1) / (1 + exp(alpha))

    Signal: spread < 0.6% means liquid enough to trade.
    """

    name = "corwin_schultz_spread"
    source = "polygon"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) < 5:
            return None

        # Use last 20 bars (or whatever is available)
        window = bars[-20:]
        spreads = []

        for i in range(1, len(window)):
            h_j = window[i].get("high", 0)
            l_j = window[i].get("low", 0)
            h_prev = window[i - 1].get("high", 0)
            l_prev = window[i - 1].get("low", 0)

            if h_j <= 0 or l_j <= 0 or h_prev <= 0 or l_prev <= 0:
                continue
            if l_j == 0 or l_prev == 0:
                continue

            # Beta: sum of squared log high/low ratios
            beta_j = math.log(h_j / l_j) ** 2
            beta_prev = math.log(h_prev / l_prev) ** 2
            beta = (beta_j + beta_prev) / 2.0

            # Gamma: squared log ratio of 2-day high/low
            h_max = max(h_j, h_prev)
            l_min = min(l_j, l_prev)
            if l_min <= 0:
                continue
            gamma = math.log(h_max / l_min) ** 2

            # Alpha
            k = 3.0 - 2.0 * math.sqrt(2.0)  # ≈ 0.1716
            if k <= 0 or beta < 0:
                continue

            sqrt_2beta = math.sqrt(2.0 * beta) if beta > 0 else 0
            sqrt_beta = math.sqrt(beta) if beta > 0 else 0
            alpha_num = sqrt_2beta - sqrt_beta
            alpha = alpha_num / k - math.sqrt(gamma / k) if k > 0 else 0

            # Spread estimate
            if alpha > -5:  # Sanity bound
                spread = 2.0 * (math.exp(alpha) - 1.0) / (1.0 + math.exp(alpha))
                spread = max(spread, 0.0)  # Spread can't be negative
                spreads.append(spread)

        if not spreads:
            return None

        return sum(spreads) / len(spreads)


class OpenInterestChange24h(BaseFeature):
    """
    24-hour change in open interest from OKX.

    Interpretation:
    - Rising price + rising OI = Bullish confidence (new money entering)
    - Rising price + falling OI = Short covering (weak rally)
    - Falling price + rising OI = Bearish confidence (new shorts)
    """

    name = "open_interest_change_24h"
    source = "okx"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        current_oi = raw_data.get("open_interest")
        if current_oi is None:
            return None

        # Compare to previous value from history
        if history and len(history) >= 1:
            prev_val = history[0].value
            if prev_val > 0:
                return (float(current_oi) - prev_val) / prev_val

        return 0.0  # No history yet — assume no change
