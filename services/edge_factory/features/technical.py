from __future__ import annotations

import math
from typing import Any

from ..models import FeatureSnapshot
from .base import BaseFeature


class GarmanKlassVol(BaseFeature):
    """
    Garman-Klass volatility estimator using OHLC data.

    More efficient than close-to-close standard deviation.

    GK = sqrt(1/N * sum(
        0.5 * ln(H/L)^2 - (2*ln(2) - 1) * ln(C/O)^2
    ))

    Returns annualized volatility (multiply by sqrt(365) for crypto).
    """

    name = "garman_klass_vol"
    source = "polygon"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) < 10:
            return None

        window = bars[-30:]  # Last 30 days
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
        annual_vol = daily_vol * math.sqrt(365)  # Crypto trades 365 days
        return annual_vol


class RSIRegimeState(BaseFeature):
    """
    RSI(14) bucketed into regime states.

    Returns:
    - 0.0: Oversold (RSI < 30)
    - 0.5: Neutral (30 <= RSI <= 70)
    - 1.0: Overbought (RSI > 70)

    Also stores raw RSI in metadata for strategy logic.
    """

    name = "rsi_regime_state"
    source = "polygon"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) < 15:
            return None

        closes = [b["close"] for b in bars[-15:] if b.get("close")]
        if len(closes) < 15:
            return None

        # Calculate RSI(14)
        gains = []
        losses = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        if len(gains) < 14:
            return None

        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        if rsi < 30:
            return 0.0  # Oversold
        elif rsi > 70:
            return 1.0  # Overbought
        else:
            return 0.5  # Neutral


class VWAPDistance(BaseFeature):
    """
    Distance of current price from approximate VWAP (%).

    VWAP = sum(price * volume) / sum(volume) over the day's bars.
    We approximate using daily close * volume.

    Signal: price > VWAP (positive distance) = bullish.
    """

    name = "vwap_distance"
    source = "polygon"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        current_price = raw_data.get("current_price", 0)
        if not bars or current_price <= 0:
            return None

        # Approximate VWAP from recent bars
        window = bars[-5:]  # 5-day VWAP
        pv_sum = 0.0
        v_sum = 0.0
        for bar in window:
            c = bar.get("close", 0)
            v = bar.get("volume", 0)
            if c > 0 and v > 0:
                pv_sum += c * v
                v_sum += v

        if v_sum <= 0:
            return None

        vwap = pv_sum / v_sum
        distance_pct = (current_price - vwap) / vwap
        return distance_pct


class ADXTrendStrength(BaseFeature):
    """
    Average Directional Index (ADX) for trend strength.

    ADX(14) computed from +DI and -DI.

    Returns normalized value:
    - ADX < 20: No trend (ranging) → 0.0-0.3
    - ADX 20-40: Trending → 0.3-0.7
    - ADX > 40: Strong trend → 0.7-1.0
    """

    name = "adx_trend_strength"
    source = "polygon"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) < 28:  # Need 2x period for smoothing
            return None

        period = 14
        window = bars[-(period * 2):]

        # Compute True Range, +DM, -DM
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []

        for i in range(1, len(window)):
            h = window[i].get("high", 0)
            l = window[i].get("low", 0)
            c_prev = window[i - 1].get("close", 0)
            h_prev = window[i - 1].get("high", 0)
            l_prev = window[i - 1].get("low", 0)

            if h <= 0 or l <= 0 or c_prev <= 0:
                continue

            tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
            tr_list.append(tr)

            up_move = h - h_prev
            down_move = l_prev - l
            plus_dm_list.append(up_move if up_move > down_move and up_move > 0 else 0)
            minus_dm_list.append(down_move if down_move > up_move and down_move > 0 else 0)

        if len(tr_list) < period:
            return None

        # Smoothed averages (Wilder's smoothing)
        atr = sum(tr_list[:period]) / period
        plus_dm_smooth = sum(plus_dm_list[:period]) / period
        minus_dm_smooth = sum(minus_dm_list[:period]) / period

        dx_list = []
        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period
            plus_dm_smooth = (plus_dm_smooth * (period - 1) + plus_dm_list[i]) / period
            minus_dm_smooth = (minus_dm_smooth * (period - 1) + minus_dm_list[i]) / period

            if atr > 0:
                plus_di = 100 * plus_dm_smooth / atr
                minus_di = 100 * minus_dm_smooth / atr
                di_sum = plus_di + minus_di
                if di_sum > 0:
                    dx = 100 * abs(plus_di - minus_di) / di_sum
                    dx_list.append(dx)

        if not dx_list:
            return None

        adx = sum(dx_list[-period:]) / min(len(dx_list), period)

        # Normalize to 0.0-1.0 (cap at 60)
        return min(adx / 60.0, 1.0)


class EfficiencyRatio(BaseFeature):
    """
    Kaufman's Efficiency Ratio.

    ER = |Price Change over N bars| / Sum of |individual bar changes|

    Measures trend "signal vs noise":
    - ER = 1.0: Perfect trend (all moves in one direction)
    - ER = 0.0: Pure noise (random walk)
    """

    name = "efficiency_ratio"
    source = "polygon"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        bars = raw_data.get("bars_daily", [])
        if len(bars) < 11:
            return None

        closes = [b["close"] for b in bars[-11:] if b.get("close")]
        if len(closes) < 11:
            return None

        period = 10
        direction = abs(closes[-1] - closes[-period - 1])
        volatility = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))

        if volatility == 0:
            return 0.0

        return direction / volatility
