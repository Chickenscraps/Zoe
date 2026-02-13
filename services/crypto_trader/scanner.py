"""Crypto candidate scanner.

Fetches bid/ask for all watchlist symbols via exchange batch API,
feeds ticks into the PriceCache, then scores each symbol using
real technical indicators (momentum, volatility, trend, RSI, EMA).

Early ticks (before enough history) use a lightweight spread-only
scoring fallback so the dashboard always has data.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from typing import Any as _ExchangeClient
from .price_cache import PriceCache

if TYPE_CHECKING:
    from .candle_manager import CandleManager


# ── Watchlist ────────────────────────────────────────────────────
WATCHLIST = [
    "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD",
]

# Minimum ticks before we trust technical indicators
MIN_TICKS_FOR_TECHNICALS = 24  # ~2h at 5-min poll interval (was 6 / 30min)


@dataclass
class CandidateScan:
    symbol: str
    score: float
    score_breakdown: dict[str, float]
    info: dict[str, Any]
    recommended_strategy: str


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ── Scoring functions ────────────────────────────────────────────

def _score_liquidity(spread_pct: float, mean_spread: float | None) -> float:
    """0-25 pts. Tighter spread + stable spread = higher score."""
    # Current spread: 0-15 pts (tighter = better)
    instant = _clamp(15 - spread_pct * 10, 0, 15)
    # Mean spread stability: 0-10 pts (only if history available)
    if mean_spread is not None:
        stability = _clamp(10 - mean_spread * 8, 0, 10)
    else:
        stability = 5.0  # neutral when no history
    return round(instant + stability, 2)


def _score_momentum(mom_short: float | None, mom_medium: float | None, ema_cross: float | None) -> float:
    """0-30 pts. Strong consistent upward momentum = higher score.

    We want to reward:
    - Positive short-term momentum (recent push)
    - Positive medium-term momentum (sustained)
    - EMA crossover bullish
    But also score mean-reversion opportunities (oversold bounces).
    """
    if mom_short is None:
        return 15.0  # neutral placeholder

    # Short momentum: -5% to +5% mapped to 0-12 pts
    short_score = _clamp((mom_short + 2) * 3, 0, 12)

    # Medium momentum: -10% to +10% mapped to 0-10 pts
    if mom_medium is not None:
        med_score = _clamp((mom_medium + 3) * 1.67, 0, 10)
    else:
        med_score = 5.0

    # EMA crossover: -1% to +1% mapped to 0-8 pts
    if ema_cross is not None:
        ema_score = _clamp((ema_cross + 0.5) * 8, 0, 8)
    else:
        ema_score = 4.0

    return round(short_score + med_score + ema_score, 2)


def _score_volatility(
    vol: float | None, spread_vol: float | None, bollinger: dict | None = None,
) -> float:
    """0-25 pts. Moderate volatility = opportunity, extreme = risk.

    Sweet spot: enough movement to profit, not so wild it's gambling.
    Bollinger Band squeeze adds bonus (breakout imminent).
    """
    if vol is None:
        return 10.0  # neutral

    # Volatility sweet spot: peak score around 30-80% annualized
    if vol < 10:
        vol_score = vol * 0.5  # too calm, low opportunity
    elif vol < 80:
        vol_score = 10.0  # sweet spot
    else:
        vol_score = _clamp(10 - (vol - 80) * 0.1, 2, 10)  # too wild

    # Spread volatility penalty: erratic spreads = unreliable fills
    if spread_vol is not None:
        spread_penalty = _clamp(spread_vol * 5, 0, 5)
    else:
        spread_penalty = 0.0

    base = vol_score + (10 - spread_penalty)

    # BB squeeze bonus: consolidation often precedes breakout
    if bollinger is not None and bollinger.get("squeeze"):
        base += 5.0

    return round(min(25.0, base), 2)


def _score_trend(trend_str: float | None, trend_dir: float | None, rsi: float | None) -> float:
    """0-25 pts. Clear trend + healthy RSI = higher score.

    Rewards:
    - Strong trend (high R²) in any direction (trend-following)
    - RSI in actionable zones (oversold for buys, not overbought)
    """
    if trend_str is None:
        return 12.5  # neutral

    # Trend strength (R²): 0-1 mapped to 0-10 pts (clear signal > noise)
    str_score = trend_str * 10

    # Trend direction: up = higher score for longs
    if trend_dir is not None:
        dir_score = _clamp((trend_dir + 0.2) * 12, 0, 8)
    else:
        dir_score = 4.0

    # RSI score: oversold (25-35) = high score, overbought (70+) = low
    if rsi is not None:
        if rsi < 30:
            rsi_score = 7.0  # oversold → bounce potential
        elif rsi < 45:
            rsi_score = 5.0  # approaching oversold
        elif rsi < 65:
            rsi_score = 4.0  # neutral zone
        elif rsi < 75:
            rsi_score = 2.0  # getting hot
        else:
            rsi_score = 0.5  # overbought → avoid
    else:
        rsi_score = 3.5

    return round(str_score + dir_score + rsi_score, 2)


def _pick_strategy(snapshot: dict[str, Any]) -> str:
    """Choose strategy based on indicators including MACD and Bollinger Bands."""
    rsi = snapshot.get("rsi")
    trend_str = snapshot.get("trend_strength")
    ema_cross = snapshot.get("ema_crossover")
    mom_med = snapshot.get("momentum_medium")
    bb = snapshot.get("bollinger")
    macd = snapshot.get("macd")

    # Not enough data → default
    if rsi is None or trend_str is None:
        spread = snapshot.get("spread_pct", 1)
        return "momentum_long" if spread < 0.3 else "mean_reversion"

    # BB squeeze + MACD expanding → breakout strategy
    if bb is not None and bb.get("squeeze") and macd is not None:
        hist = macd.get("histogram", 0)
        slope = macd.get("histogram_slope", 0)
        if hist > 0 and slope > 0:
            return "bb_breakout_long"

    # BB oversold + RSI oversold → mean reversion bounce
    if bb is not None and bb.get("percent_b", 0.5) < 0.15 and rsi < 35:
        return "bb_mean_reversion_long"

    # Oversold bounce play
    if rsi < 30:
        return "mean_reversion_long"

    # Overbought — potential short or avoid
    if rsi > 75:
        return "take_profit"

    # Strong trend with EMA confirmation
    if trend_str > 0.6 and ema_cross is not None and ema_cross > 0.05:
        return "trend_follow_long"

    # Weak trend, moderate RSI → range/mean-reversion
    if trend_str < 0.3:
        return "mean_reversion"

    # Default: momentum if positive, otherwise hold
    if mom_med is not None and mom_med > 0.3:
        return "momentum_long"

    return "hold"


# ── Main scanner ─────────────────────────────────────────────────

async def scan_candidates(
    client: Any,
    price_cache: PriceCache,
    candle_manager: CandleManager | None = None,
) -> list[CandidateScan]:
    """Fetch prices, update cache, score all watchlist symbols.

    Uses batch API when available, falls back to sequential.
    """
    candidates: list[CandidateScan] = []

    # Try batch fetch first (one API call for all symbols)
    bid_ask_map: dict[str, tuple[float, float]] = {}
    try:
        batch = await client.get_best_bid_ask_batch(WATCHLIST)
        for result in batch.get("results", []):
            symbol = result.get("symbol", "")
            bid = float(result.get("bid_inclusive_of_sell_spread", result.get("bid_price", 0)))
            ask = float(result.get("ask_inclusive_of_buy_spread", result.get("ask_price", 0)))
            if bid > 0 and ask > 0:
                bid_ask_map[symbol] = (bid, ask)
    except Exception:
        # Batch failed — fall back to sequential
        pass

    # Fill in any symbols missing from batch
    for symbol in WATCHLIST:
        if symbol in bid_ask_map:
            continue
        try:
            data = await client.get_best_bid_ask(symbol)
            results = data.get("results", [data] if "bid_price" in data else [])
            if results:
                quote = results[0]
                bid = float(quote.get("bid_inclusive_of_sell_spread", quote.get("bid_price", 0)))
                ask = float(quote.get("ask_inclusive_of_buy_spread", quote.get("ask_price", 0)))
                if bid > 0 and ask > 0:
                    bid_ask_map[symbol] = (bid, ask)
            await asyncio.sleep(0.15)  # rate limit courtesy
        except Exception:
            continue

    # Record ticks in price cache and score
    for symbol in WATCHLIST:
        if symbol not in bid_ask_map:
            continue

        bid, ask = bid_ask_map[symbol]
        price_cache.record(symbol, bid, ask)
        snap = price_cache.snapshot(symbol)

        has_technicals = price_cache.has_enough_data(symbol, MIN_TICKS_FOR_TECHNICALS)

        # Score components
        liq_score = _score_liquidity(snap["spread_pct"], snap["mean_spread"])
        mom_score = _score_momentum(snap["momentum_short"], snap["momentum_medium"], snap["ema_crossover"])
        vol_score = _score_volatility(snap["volatility"], snap["spread_volatility"], snap.get("bollinger"))
        trend_score = _score_trend(snap["trend_strength"], snap["trend_direction"], snap["rsi"])

        total = round(liq_score + mom_score + vol_score + trend_score, 1)
        strategy = _pick_strategy(snap)

        # Chart analysis: patterns + multi-timeframe (if candle_manager available)
        chart_info: dict[str, Any] = {}
        if candle_manager is not None:
            try:
                from .patterns import detect_patterns, detect_support_resistance
                from .mtf_analyzer import analyze_mtf

                # Pattern detection on 1h candles (most reliable timeframe)
                candles_1h = candle_manager.get_candles(symbol, "1h")
                patterns = detect_patterns(candles_1h, lookback=5) if len(candles_1h) >= 3 else []
                sr_levels = detect_support_resistance(candles_1h) if len(candles_1h) >= 10 else []

                # Multi-timeframe analysis
                mtf = analyze_mtf(candle_manager, symbol)

                # Golden/Death Cross detection
                from .mtf_analyzer import detect_golden_death_cross
                cross = detect_golden_death_cross(candle_manager, symbol, "4h")

                # Divergence detection on 1h candles
                divs = candle_manager.compute_divergences(symbol, "1h")

                chart_info = {
                    "patterns": [p.to_dict() for p in patterns[:5]],  # top 5
                    "mtf_alignment": round(mtf.alignment_score, 3),
                    "mtf_dominant_trend": mtf.dominant_trend,
                    "mtf_details": [tf.to_dict() for tf in mtf.timeframes],
                    "support_levels": [l.to_dict() for l in sr_levels if l.level_type == "support"][:3],
                    "resistance_levels": [l.to_dict() for l in sr_levels if l.level_type == "resistance"][:3],
                    "candle_counts": {
                        tf: candle_manager.candle_count(symbol, tf)
                        for tf in ["15m", "1h", "4h"]
                    },
                    "golden_death_cross": cross,
                    "divergences": [d.to_dict() for d in divs[:3]],
                }
            except Exception:
                pass  # chart analysis is non-critical

        candidates.append(CandidateScan(
            symbol=symbol,
            score=total,
            score_breakdown={
                "liquidity": liq_score,
                "momentum": mom_score,
                "volatility": vol_score,
                "trend": trend_score,
            },
            info={
                "bid": bid,
                "ask": ask,
                "mid": round(snap["mid"], 8),
                "spread_pct": round(snap["spread_pct"], 4),
                "tick_count": snap["tick_count"],
                "has_technicals": has_technicals,
                "rsi": round(snap["rsi"], 1) if snap["rsi"] is not None else None,
                "momentum_short": round(snap["momentum_short"], 4) if snap["momentum_short"] is not None else None,
                "momentum_medium": round(snap["momentum_medium"], 4) if snap["momentum_medium"] is not None else None,
                "ema_crossover": round(snap["ema_crossover"], 4) if snap["ema_crossover"] is not None else None,
                "volatility_ann": round(snap["volatility"], 2) if snap["volatility"] is not None else None,
                "trend_strength": round(snap["trend_strength"], 3) if snap["trend_strength"] is not None else None,
                "macd": snap.get("macd"),
                "bollinger": snap.get("bollinger"),
                **chart_info,
            },
            recommended_strategy=strategy,
        ))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates
