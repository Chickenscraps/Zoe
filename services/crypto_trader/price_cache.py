"""In-memory price tick cache with ring buffer per symbol.

Accumulates bid/ask snapshots from repeated API polls to enable
real technical analysis (momentum, volatility, trend) without
needing a historicals API endpoint.

Each tick stores: timestamp, bid, ask, mid, spread_pct.
Default capacity: 288 ticks per symbol (24h at 5-min intervals).
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PriceTick:
    """Single bid/ask observation."""
    ts: float          # Unix timestamp
    bid: float
    ask: float
    mid: float
    spread_pct: float  # (ask - bid) / mid * 100


@dataclass
class SymbolHistory:
    """Ring buffer of price ticks for one symbol."""
    ticks: deque[PriceTick]
    capacity: int

    def __init__(self, capacity: int = 288) -> None:
        self.capacity = capacity
        self.ticks = deque(maxlen=capacity)

    def push(self, tick: PriceTick) -> None:
        self.ticks.append(tick)

    @property
    def count(self) -> int:
        return len(self.ticks)

    @property
    def latest(self) -> PriceTick | None:
        return self.ticks[-1] if self.ticks else None

    def mids(self, n: int | None = None) -> list[float]:
        """Return last n mid prices (or all)."""
        if n is None:
            return [t.mid for t in self.ticks]
        return [t.mid for t in list(self.ticks)[-n:]]

    def spreads(self, n: int | None = None) -> list[float]:
        """Return last n spread percentages."""
        if n is None:
            return [t.spread_pct for t in self.ticks]
        return [t.spread_pct for t in list(self.ticks)[-n:]]

    def age_seconds(self) -> float:
        """Time span from oldest to newest tick."""
        if len(self.ticks) < 2:
            return 0.0
        return self.ticks[-1].ts - self.ticks[0].ts


class PriceCache:
    """Global price cache — one SymbolHistory per watched symbol."""

    def __init__(self, capacity_per_symbol: int = 288) -> None:
        self._capacity = capacity_per_symbol
        self._symbols: dict[str, SymbolHistory] = {}
        self._candle_manager: Any | None = None  # Optional CandleManager reference

    def set_candle_manager(self, candle_manager: Any) -> None:
        """Wire a CandleManager to receive ticks for candle aggregation."""
        self._candle_manager = candle_manager

    def record(self, symbol: str, bid: float, ask: float, ts: float | None = None) -> PriceTick:
        """Record a new bid/ask observation. Returns the created tick."""
        if symbol not in self._symbols:
            self._symbols[symbol] = SymbolHistory(self._capacity)
        mid = (bid + ask) / 2
        spread_pct = ((ask - bid) / mid) * 100 if mid > 0 else 999.0
        tick = PriceTick(ts=ts or time.time(), bid=bid, ask=ask, mid=mid, spread_pct=spread_pct)
        self._symbols[symbol].push(tick)

        # Feed tick into candle aggregation if wired
        if self._candle_manager is not None:
            self._candle_manager.ingest_tick(symbol, mid, tick.ts)

        return tick

    def get(self, symbol: str) -> SymbolHistory | None:
        return self._symbols.get(symbol)

    def has_enough_data(self, symbol: str, min_ticks: int = 6) -> bool:
        """Need at least min_ticks for meaningful analysis (6 ticks = 30min at 5-min intervals)."""
        hist = self._symbols.get(symbol)
        return hist is not None and hist.count >= min_ticks

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols.keys())

    # ── Technical indicators ─────────────────────────────────────

    def momentum(self, symbol: str, lookback: int = 12) -> float | None:
        """Price momentum: % change over last `lookback` ticks.

        Default lookback=12 = 1 hour at 5-min intervals.
        Returns: percent change (positive = up, negative = down).
        """
        hist = self._symbols.get(symbol)
        if not hist or hist.count < lookback + 1:
            return None
        mids = hist.mids(lookback + 1)
        old, new = mids[0], mids[-1]
        if old == 0:
            return None
        return ((new - old) / old) * 100

    def momentum_short(self, symbol: str) -> float | None:
        """Short-term momentum: % change over last 3 ticks (~15 min)."""
        return self.momentum(symbol, lookback=3)

    def momentum_medium(self, symbol: str) -> float | None:
        """Medium-term momentum: % change over last 12 ticks (~1 hour)."""
        return self.momentum(symbol, lookback=12)

    def momentum_long(self, symbol: str) -> float | None:
        """Long-term momentum: % change over last 48 ticks (~4 hours)."""
        return self.momentum(symbol, lookback=48)

    def volatility(self, symbol: str, lookback: int = 12) -> float | None:
        """Realized volatility: std dev of tick-to-tick returns over lookback.

        Returns annualized volatility estimate (assuming 5-min ticks, 288/day).
        """
        hist = self._symbols.get(symbol)
        if not hist or hist.count < lookback + 1:
            return None
        mids = hist.mids(lookback + 1)
        returns = []
        for i in range(1, len(mids)):
            if mids[i - 1] > 0:
                returns.append((mids[i] - mids[i - 1]) / mids[i - 1])
        if len(returns) < 2:
            return None
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(var_r)
        # Annualize: sqrt(ticks_per_day) * tick_std
        return std_r * math.sqrt(288) * 100  # as percentage

    def trend_strength(self, symbol: str, lookback: int = 12) -> float | None:
        """Trend strength: linear regression R² of mid prices.

        Returns 0-1 where 1 = perfect straight line (strong trend).
        """
        hist = self._symbols.get(symbol)
        if not hist or hist.count < lookback:
            return None
        mids = hist.mids(lookback)
        n = len(mids)
        if n < 3:
            return None
        # Simple linear regression R²
        x_mean = (n - 1) / 2
        y_mean = sum(mids) / n
        ss_xy = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(mids))
        ss_xx = sum((i - x_mean) ** 2 for i in range(n))
        ss_yy = sum((y - y_mean) ** 2 for y in mids)
        if ss_xx == 0 or ss_yy == 0:
            return 0.0
        r_squared = (ss_xy ** 2) / (ss_xx * ss_yy)
        return r_squared

    def trend_direction(self, symbol: str, lookback: int = 12) -> float | None:
        """Trend direction: slope sign.

        Returns positive = uptrend, negative = downtrend, magnitude = steepness.
        """
        hist = self._symbols.get(symbol)
        if not hist or hist.count < lookback:
            return None
        mids = hist.mids(lookback)
        n = len(mids)
        if n < 3:
            return None
        x_mean = (n - 1) / 2
        y_mean = sum(mids) / n
        ss_xy = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(mids))
        ss_xx = sum((i - x_mean) ** 2 for i in range(n))
        if ss_xx == 0:
            return 0.0
        slope = ss_xy / ss_xx
        # Normalize as percent of mean price per tick
        return (slope / y_mean) * 100 if y_mean > 0 else 0.0

    def mean_spread(self, symbol: str, lookback: int = 12) -> float | None:
        """Average spread % over recent ticks — measures liquidity stability."""
        hist = self._symbols.get(symbol)
        if not hist or hist.count < lookback:
            return None
        spreads = hist.spreads(lookback)
        return sum(spreads) / len(spreads) if spreads else None

    def spread_volatility(self, symbol: str, lookback: int = 12) -> float | None:
        """Std dev of spread % — erratic spreads = unstable liquidity."""
        hist = self._symbols.get(symbol)
        if not hist or hist.count < lookback:
            return None
        spreads = hist.spreads(lookback)
        if len(spreads) < 2:
            return None
        mean_s = sum(spreads) / len(spreads)
        var_s = sum((s - mean_s) ** 2 for s in spreads) / (len(spreads) - 1)
        return math.sqrt(var_s)

    def ema(self, symbol: str, span: int = 12) -> float | None:
        """Exponential moving average of mid prices.

        span=12 → ~1hr EMA at 5-min ticks.
        """
        hist = self._symbols.get(symbol)
        if not hist or hist.count < span:
            return None
        mids = hist.mids()
        alpha = 2 / (span + 1)
        ema_val = mids[0]
        for price in mids[1:]:
            ema_val = alpha * price + (1 - alpha) * ema_val
        return ema_val

    def ema_crossover(self, symbol: str, fast: int = 6, slow: int = 24) -> float | None:
        """EMA crossover signal: (fast_ema - slow_ema) / slow_ema * 100.

        Positive = fast above slow (bullish), negative = bearish.
        fast=6 (~30min), slow=24 (~2hr) at 5-min ticks.
        """
        fast_ema = self.ema(symbol, fast)
        slow_ema = self.ema(symbol, slow)
        if fast_ema is None or slow_ema is None or slow_ema == 0:
            return None
        return ((fast_ema - slow_ema) / slow_ema) * 100

    def rsi(self, symbol: str, period: int = 14) -> float | None:
        """Relative Strength Index (0-100).

        period=14 ticks is standard RSI; at 5-min intervals = ~70 minutes.
        """
        hist = self._symbols.get(symbol)
        if not hist or hist.count < period + 1:
            return None
        mids = hist.mids(period + 1)
        gains = []
        losses = []
        for i in range(1, len(mids)):
            change = mids[i] - mids[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    # ── MACD ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_ema_series(values: list[float], span: int) -> list[float]:
        """Compute full EMA series from a list of values.

        Returns a list the same length as `values` with EMA at each point.
        Reusable helper for MACD, Bollinger, and other composite indicators.
        """
        if len(values) < span:
            return []
        alpha = 2 / (span + 1)
        result = [values[0]]
        for price in values[1:]:
            result.append(alpha * price + (1 - alpha) * result[-1])
        return result

    def macd(
        self, symbol: str, fast: int = 12, slow: int = 26, signal: int = 9,
    ) -> dict[str, Any] | None:
        """Moving Average Convergence Divergence.

        Returns dict with:
            macd_line:       fast EMA − slow EMA
            signal_line:     9-period EMA of the MACD line series
            histogram:       macd_line − signal_line
            histogram_slope: current histogram − previous histogram
                             (positive = momentum accelerating)
            crossover:       +1 bullish, −1 bearish, 0 none
        """
        hist = self._symbols.get(symbol)
        if not hist or hist.count < slow + signal:
            return None

        mids = hist.mids()
        fast_series = self._compute_ema_series(mids, fast)
        slow_series = self._compute_ema_series(mids, slow)

        if len(fast_series) < slow + signal or len(slow_series) < slow + signal:
            return None

        # MACD line series (fast EMA − slow EMA)
        macd_series = [f - s for f, s in zip(fast_series, slow_series)]

        # Signal line: EMA of MACD line (use only from index `slow-1` onward
        # where the slow EMA has warmed up)
        warmed = macd_series[slow - 1:]
        if len(warmed) < signal:
            return None
        signal_series = self._compute_ema_series(warmed, signal)

        macd_line = macd_series[-1]
        signal_line = signal_series[-1]
        histogram = macd_line - signal_line

        # Histogram slope (momentum acceleration / deceleration)
        prev_histogram = macd_series[-2] - signal_series[-2] if len(signal_series) >= 2 else 0.0
        histogram_slope = histogram - prev_histogram

        # Crossover detection
        crossover = 0
        if len(signal_series) >= 2:
            if prev_histogram <= 0 < histogram:
                crossover = 1   # bullish crossover
            elif prev_histogram >= 0 > histogram:
                crossover = -1  # bearish crossover

        return {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram,
            "histogram_slope": histogram_slope,
            "crossover": crossover,
        }

    def macd_crypto(self, symbol: str) -> dict[str, Any] | None:
        """MACD with crypto-optimized parameters (8/17/9).

        Faster settings capture sharper momentum shifts common in 24/7
        crypto markets, per quantitative research recommendations.
        """
        return self.macd(symbol, fast=8, slow=17, signal=9)

    # ── Bollinger Bands ───────────────────────────────────────────

    def bollinger_bands(
        self, symbol: str, period: int = 20, std_dev: float = 2.0,
    ) -> dict[str, Any] | None:
        """Bollinger Bands: SMA ± (std_dev × σ).

        Returns dict with:
            upper:     upper band
            middle:    20-period SMA (center line)
            lower:     lower band
            bandwidth: (upper − lower) / middle × 100  (volatility measure)
            percent_b: (price − lower) / (upper − lower)
                       0 = at lower band, 0.5 = at middle, 1 = at upper
            squeeze:   True when bandwidth is in lowest 20th percentile
                       of recent 50 readings (breakout imminent)
        """
        hist = self._symbols.get(symbol)
        if not hist or hist.count < period:
            return None

        mids = hist.mids()
        recent = mids[-period:]

        # SMA (middle band)
        sma = sum(recent) / period

        # Population standard deviation over the window
        variance = sum((p - sma) ** 2 for p in recent) / period
        stddev = math.sqrt(variance)

        upper = sma + std_dev * stddev
        lower = sma - std_dev * stddev
        current = mids[-1]

        # Bandwidth: measures current volatility regime
        bandwidth = ((upper - lower) / sma) * 100 if sma > 0 else 0.0

        # %B: where price sits within the bands
        band_range = upper - lower
        percent_b = (current - lower) / band_range if band_range > 0 else 0.5

        # Squeeze detection: bandwidth in lowest 20th percentile of
        # recent 50 bandwidth readings.  Low bandwidth → consolidation →
        # high probability of directional breakout.
        squeeze = False
        if hist.count >= period + 50:
            bw_history: list[float] = []
            for end in range(len(mids) - 50, len(mids)):
                window = mids[max(0, end - period + 1) : end + 1]
                if len(window) == period:
                    w_sma = sum(window) / period
                    w_std = math.sqrt(sum((p - w_sma) ** 2 for p in window) / period)
                    w_bw = ((2 * std_dev * w_std) / w_sma * 100) if w_sma > 0 else 0.0
                    bw_history.append(w_bw)
            if bw_history:
                threshold_idx = max(1, len(bw_history) // 5)  # 20th percentile
                squeeze = bandwidth <= sorted(bw_history)[threshold_idx]

        return {
            "upper": upper,
            "middle": sma,
            "lower": lower,
            "bandwidth": bandwidth,
            "percent_b": percent_b,
            "squeeze": squeeze,
        }

    def snapshot(self, symbol: str) -> dict[str, Any]:
        """Full technical snapshot for a symbol — used by scanner."""
        hist = self._symbols.get(symbol)
        tick = hist.latest if hist else None
        has_data = self.has_enough_data(symbol, min_ticks=6)

        return {
            "tick_count": hist.count if hist else 0,
            "age_seconds": hist.age_seconds() if hist else 0,
            "bid": tick.bid if tick else 0,
            "ask": tick.ask if tick else 0,
            "mid": tick.mid if tick else 0,
            "spread_pct": tick.spread_pct if tick else 0,
            # Indicators (None if not enough data)
            "momentum_short": self.momentum_short(symbol) if has_data else None,
            "momentum_medium": self.momentum_medium(symbol) if has_data else None,
            "momentum_long": self.momentum_long(symbol) if has_data else None,
            "volatility": self.volatility(symbol) if has_data else None,
            "trend_strength": self.trend_strength(symbol) if has_data else None,
            "trend_direction": self.trend_direction(symbol) if has_data else None,
            "mean_spread": self.mean_spread(symbol) if has_data else None,
            "spread_volatility": self.spread_volatility(symbol) if has_data else None,
            "ema_crossover": self.ema_crossover(symbol) if has_data else None,
            "rsi": self.rsi(symbol) if has_data else None,
            "macd": self.macd(symbol) if has_data else None,
            "macd_crypto": self.macd_crypto(symbol) if has_data else None,
            "bollinger": self.bollinger_bands(symbol) if has_data else None,
        }
