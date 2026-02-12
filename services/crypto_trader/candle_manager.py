"""Candle aggregation engine — converts raw ticks into OHLCV candles.

Aggregates bid/ask ticks from the PriceCache into multi-timeframe
candlestick data (15m, 1h, 4h). Also fetches historical OHLC from
CoinGecko free API to seed longer timeframes on startup.

Each finalized candle is stored in a deque (last 100 per symbol/tf)
and can be persisted to Supabase for dashboard visualization.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import aiohttp


# ── Symbol mapping for CoinGecko ────────────────────────────────
COINGECKO_IDS: dict[str, str] = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "DOGE-USD": "dogecoin",
    "SOL-USD": "solana",
    "SHIB-USD": "shiba-inu",
    "AVAX-USD": "avalanche-2",
    "LINK-USD": "chainlink",
    "XLM-USD": "stellar",
    "LTC-USD": "litecoin",
    "UNI-USD": "uniswap",
}

# Timeframe durations in seconds
TIMEFRAMES: dict[str, int] = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
}

MAX_CANDLES_PER_SERIES = 100


@dataclass(frozen=True)
class Candle:
    """Single OHLCV candle."""
    symbol: str
    timeframe: str
    open_time: float      # Unix timestamp of candle open
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    is_final: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open_time": self.open_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "is_final": self.is_final,
        }


@dataclass
class _LiveCandle:
    """Mutable in-progress candle being built from ticks."""
    open_time: float
    open: float
    high: float
    low: float
    close: float
    tick_count: int = 0

    def update(self, price: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.tick_count += 1


class CandleManager:
    """Aggregates ticks into multi-timeframe OHLCV candles."""

    def __init__(self) -> None:
        # Finalized candles: {(symbol, timeframe): deque[Candle]}
        self._candles: dict[tuple[str, str], deque[Candle]] = {}
        # In-progress candles: {(symbol, timeframe): _LiveCandle}
        self._live: dict[tuple[str, str], _LiveCandle] = {}
        # Newly finalized candles waiting to be persisted
        self._pending_persist: list[Candle] = []

    def _get_series(self, symbol: str, tf: str) -> deque[Candle]:
        key = (symbol, tf)
        if key not in self._candles:
            self._candles[key] = deque(maxlen=MAX_CANDLES_PER_SERIES)
        return self._candles[key]

    def _candle_open_time(self, ts: float, tf_seconds: int) -> float:
        """Compute the candle open time by flooring ts to the timeframe boundary."""
        return (ts // tf_seconds) * tf_seconds

    def ingest_tick(self, symbol: str, price: float, ts: float | None = None) -> None:
        """Feed a price tick into all timeframe candle buffers.

        Called from PriceCache.record() on every bid/ask update.
        """
        ts = ts or time.time()

        for tf_name, tf_seconds in TIMEFRAMES.items():
            key = (symbol, tf_name)
            candle_open = self._candle_open_time(ts, tf_seconds)

            live = self._live.get(key)

            if live is None:
                # Start new candle
                self._live[key] = _LiveCandle(
                    open_time=candle_open,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    tick_count=1,
                )
            elif candle_open > live.open_time:
                # Current candle period ended — finalize it
                finalized = Candle(
                    symbol=symbol,
                    timeframe=tf_name,
                    open_time=live.open_time,
                    open=live.open,
                    high=live.high,
                    low=live.low,
                    close=live.close,
                    is_final=True,
                )
                self._get_series(symbol, tf_name).append(finalized)
                self._pending_persist.append(finalized)

                # Start new candle
                self._live[key] = _LiveCandle(
                    open_time=candle_open,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    tick_count=1,
                )
            else:
                # Update current candle
                live.update(price)

    def get_candles(self, symbol: str, timeframe: str, limit: int | None = None) -> list[Candle]:
        """Get finalized candles for a symbol/timeframe.

        Returns candles sorted by open_time ascending.
        Optionally includes the current in-progress candle at the end.
        """
        series = self._get_series(symbol, timeframe)
        candles = list(series)

        # Append current live candle as non-final
        key = (symbol, timeframe)
        live = self._live.get(key)
        if live is not None:
            candles.append(Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time=live.open_time,
                open=live.open,
                high=live.high,
                low=live.low,
                close=live.close,
                is_final=False,
            ))

        if limit is not None:
            candles = candles[-limit:]
        return candles

    def get_closes(self, symbol: str, timeframe: str, limit: int | None = None) -> list[float]:
        """Get close prices for finalized candles (used for indicators)."""
        series = self._get_series(symbol, timeframe)
        closes = [c.close for c in series]
        if limit is not None:
            closes = closes[-limit:]
        return closes

    def drain_pending(self) -> list[Candle]:
        """Pop all newly finalized candles waiting for Supabase persistence."""
        pending = self._pending_persist
        self._pending_persist = []
        return pending

    def candle_count(self, symbol: str, timeframe: str) -> int:
        """Number of finalized candles available."""
        return len(self._get_series(symbol, timeframe))

    def compute_divergences(self, symbol: str, timeframe: str = "1h") -> list:
        """Detect price/indicator divergences on candles.

        Computes RSI and MACD histogram series from candle closes,
        then runs divergence detection for both.

        Returns list of Divergence objects (from divergence.py).
        """
        from .divergence import detect_rsi_divergence, detect_macd_divergence
        from .mtf_analyzer import _rsi_from_closes, _macd_from_closes

        closes = self.get_closes(symbol, timeframe)
        if len(closes) < 30:
            return []

        divergences = []

        # RSI divergence
        # Build RSI series aligned to closes (pad leading None→skip)
        rsi_series: list[float] = []
        for i in range(len(closes)):
            rsi_val = _rsi_from_closes(closes[: i + 1], period=14)
            rsi_series.append(rsi_val if rsi_val is not None else 50.0)  # neutral pad

        divergences.extend(detect_rsi_divergence(closes, rsi_series))

        # MACD histogram divergence
        macd_result = _macd_from_closes(closes, fast=12, slow=26, signal=9)
        if macd_result is not None:
            # Build full MACD histogram series
            from .price_cache import PriceCache
            fast_s = PriceCache._compute_ema_series(closes, 12)
            slow_s = PriceCache._compute_ema_series(closes, 26)
            if fast_s and slow_s:
                macd_line_series = [f - s for f, s in zip(fast_s, slow_s)]
                warmed = macd_line_series[25:]  # after slow EMA warms up
                if len(warmed) >= 9:
                    sig_s = PriceCache._compute_ema_series(warmed, 9)
                    hist_series = [m - s for m, s in zip(warmed, sig_s)]
                    # Pad to match closes length
                    pad_len = len(closes) - len(hist_series)
                    padded_hist = [0.0] * pad_len + hist_series
                    divergences.extend(detect_macd_divergence(closes, padded_hist))

        return divergences

    # ── Historical data loading (CoinGecko) ────────────────────

    async def load_historical(self, symbols: list[str] | None = None) -> int:
        """Fetch 7-day OHLC from CoinGecko to seed candle history.

        Returns total candles loaded.
        """
        symbols = symbols or list(COINGECKO_IDS.keys())
        total = 0

        async with aiohttp.ClientSession() as session:
            for symbol in symbols:
                cg_id = COINGECKO_IDS.get(symbol)
                if not cg_id:
                    continue
                try:
                    loaded = await self._fetch_coingecko_ohlc(session, symbol, cg_id)
                    total += loaded
                    # Rate limit: CoinGecko free tier ~10-30 req/min
                    await asyncio.sleep(2.5)
                except Exception as e:
                    print(f"[CANDLE] CoinGecko fetch failed for {symbol}: {e}")

        print(f"[CANDLE] Historical load complete: {total} candles across {len(symbols)} symbols")
        return total

    async def _fetch_coingecko_ohlc(self, session: aiohttp.ClientSession, symbol: str, cg_id: str) -> int:
        """Fetch 7-day OHLC from CoinGecko and seed 4h candles."""
        url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/ohlc"
        params = {"vs_currency": "usd", "days": "7"}

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                print(f"[CANDLE] CoinGecko {symbol}: HTTP {resp.status}")
                return 0
            data = await resp.json()

        if not isinstance(data, list):
            return 0

        count = 0
        for point in data:
            # CoinGecko OHLC format: [timestamp_ms, open, high, low, close]
            if len(point) < 5:
                continue
            ts_ms, o, h, l, c = point[0], point[1], point[2], point[3], point[4]
            ts = ts_ms / 1000.0

            # CoinGecko 7-day OHLC returns ~4h candles
            candle = Candle(
                symbol=symbol,
                timeframe="4h",
                open_time=ts,
                open=float(o),
                high=float(h),
                low=float(l),
                close=float(c),
                is_final=True,
            )
            self._get_series(symbol, "4h").append(candle)
            count += 1

        # Also build 1h approximations by subdividing (if we have enough data)
        # The 4h data is the best we get from free CoinGecko
        print(f"[CANDLE] {symbol}: loaded {count} historical 4h candles from CoinGecko")
        return count
