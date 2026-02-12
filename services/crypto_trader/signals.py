"""Signal engine — converts scanner output into actionable trade decisions.

Pipeline: Scanner → Signals → Trader
    scan_candidates() → generate_signals() → trader auto-executes or logs

Each signal has:
    - action: BUY / SELL / HOLD
    - confidence: 0-1 (how certain we are)
    - reason: human-readable explanation
    - sizing: suggested notional amount

The engine respects risk rules:
    - Never signals BUY when RSI > 75 (overbought)
    - Never signals BUY with negative medium-term momentum + weak trend
    - Reduces confidence when volatility is extreme
    - Requires MIN_CONFIDENCE to emit actionable signal
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .scanner import CandidateScan
from .price_cache import PriceCache


# ── Configuration ────────────────────────────────────────────────

# Minimum confidence to surface a signal (below this → HOLD)
MIN_CONFIDENCE_BUY = 0.65
MIN_CONFIDENCE_SELL = 0.60

# Max notional per signal (overridable by trader config)
DEFAULT_SIGNAL_NOTIONAL = 5.0

# Score thresholds (out of 100)
HIGH_SCORE_THRESHOLD = 72
LOW_SCORE_THRESHOLD = 35


@dataclass
class Signal:
    """A trade signal produced by the engine."""
    symbol: str
    action: str          # "BUY" | "SELL" | "HOLD"
    confidence: float    # 0.0 - 1.0
    reason: str
    strategy: str
    suggested_notional: float
    score: float
    indicators: dict[str, Any]

    @property
    def is_actionable(self) -> bool:
        if self.action == "BUY":
            return self.confidence >= MIN_CONFIDENCE_BUY
        if self.action == "SELL":
            return self.confidence >= MIN_CONFIDENCE_SELL
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "strategy": self.strategy,
            "suggested_notional": self.suggested_notional,
            "score": self.score,
            "is_actionable": self.is_actionable,
            "indicators": self.indicators,
        }


# ── Signal generation ────────────────────────────────────────────

def _compute_buy_confidence(candidate: CandidateScan, snap: dict[str, Any]) -> tuple[float, str]:
    """Compute BUY confidence + reason from candidate + price snapshot."""
    score = candidate.score
    rsi = snap.get("rsi")
    mom_short = snap.get("momentum_short")
    mom_med = snap.get("momentum_medium")
    trend_str = snap.get("trend_strength")
    trend_dir = snap.get("trend_direction")
    ema_cross = snap.get("ema_crossover")
    vol = snap.get("volatility")
    spread = snap.get("spread_pct", 1.0)
    has_technicals = snap.get("tick_count", 0) >= 6

    confidence = 0.0
    reasons = []

    # ── Hard vetoes (return 0) ──
    if rsi is not None and rsi > 78:
        return 0.0, "RSI overbought (>78) — no buy"
    if spread > 2.0:
        return 0.0, "Spread too wide (>2%) — illiquid"
    if vol is not None and vol > 200:
        return 0.0, "Extreme volatility (>200% ann.) — too risky"

    # ── Base confidence from total score (0-100 mapped to 0.0-0.5) ──
    confidence += min(0.5, score / 200)

    # ── Momentum boost ──
    if mom_short is not None and mom_short > 0.1:
        boost = min(0.15, mom_short * 0.03)
        confidence += boost
        reasons.append(f"short momentum +{mom_short:.2f}%")

    if mom_med is not None and mom_med > 0.2:
        boost = min(0.1, mom_med * 0.02)
        confidence += boost
        reasons.append(f"medium momentum +{mom_med:.2f}%")

    # ── Trend confirmation ──
    if trend_str is not None and trend_str > 0.5 and trend_dir is not None and trend_dir > 0:
        confidence += 0.1
        reasons.append(f"strong uptrend (R²={trend_str:.2f})")

    # ── EMA crossover ──
    if ema_cross is not None and ema_cross > 0.05:
        confidence += 0.08
        reasons.append(f"EMA crossover bullish ({ema_cross:.3f}%)")

    # ── RSI oversold bounce ──
    if rsi is not None and rsi < 32:
        confidence += 0.12
        reasons.append(f"RSI oversold ({rsi:.0f}) — bounce potential")
    elif rsi is not None and rsi < 45:
        confidence += 0.05
        reasons.append(f"RSI favorable ({rsi:.0f})")

    # ── Liquidity bonus ──
    if spread < 0.15:
        confidence += 0.05
        reasons.append(f"tight spread ({spread:.3f}%)")

    # ── Chart pattern boosts (from candle analysis) ──
    patterns = snap.get("patterns", [])
    mtf_alignment = snap.get("mtf_alignment")
    support_levels = snap.get("support_levels", [])
    resistance_levels = snap.get("resistance_levels", [])
    current_price = snap.get("mid", 0)

    # Bullish reversal patterns boost buy confidence
    bullish_patterns = [p for p in patterns if p.get("direction") == "bullish"]
    if bullish_patterns:
        best = max(bullish_patterns, key=lambda p: p.get("strength", 0))
        pattern_boost = min(0.12, best.get("strength", 0) * 0.15)
        confidence += pattern_boost
        reasons.append(f"bullish pattern: {best.get('name')} ({best.get('strength', 0):.0%})")

    # Bearish patterns penalize buy
    bearish_patterns = [p for p in patterns if p.get("direction") == "bearish"]
    if bearish_patterns:
        confidence *= 0.7
        reasons.append(f"bearish pattern detected: {bearish_patterns[0].get('name')}")

    # MTF alignment boost
    if mtf_alignment is not None:
        if mtf_alignment > 0.5:
            confidence += 0.10
            reasons.append(f"MTF aligned bullish ({mtf_alignment:+.2f})")
        elif mtf_alignment > 0.2:
            confidence += 0.05
            reasons.append(f"MTF leaning bullish ({mtf_alignment:+.2f})")
        elif mtf_alignment < -0.3:
            confidence *= 0.8
            reasons.append(f"MTF bearish ({mtf_alignment:+.2f})")

    # Support/resistance proximity
    if current_price > 0 and support_levels:
        nearest_support = min(support_levels, key=lambda l: abs(l.get("price", 0) - current_price))
        dist_pct = abs(current_price - nearest_support.get("price", 0)) / current_price * 100
        if dist_pct < 1.0:
            confidence += 0.06
            reasons.append(f"near support ${nearest_support.get('price', 0):,.0f}")

    if current_price > 0 and resistance_levels:
        nearest_resistance = min(resistance_levels, key=lambda l: abs(l.get("price", 0) - current_price))
        dist_pct = abs(current_price - nearest_resistance.get("price", 0)) / current_price * 100
        if dist_pct < 1.0:
            confidence *= 0.85
            reasons.append(f"near resistance ${nearest_resistance.get('price', 0):,.0f}")

    # ── Penalties ──
    if not has_technicals:
        confidence *= 0.6  # reduce when working with limited data
        reasons.append("limited price history — reduced confidence")

    if vol is not None and vol > 120:
        confidence *= 0.85
        reasons.append(f"high volatility penalty ({vol:.0f}%)")

    if mom_med is not None and mom_med < -1.0 and (trend_str is None or trend_str < 0.4):
        confidence *= 0.7
        reasons.append("negative momentum + weak trend")

    # Clamp
    confidence = min(1.0, max(0.0, confidence))
    reason = "; ".join(reasons) if reasons else f"score={score:.0f}"
    return confidence, reason


def _compute_sell_confidence(candidate: CandidateScan, snap: dict[str, Any], has_position: bool) -> tuple[float, str]:
    """Compute SELL confidence for take-profit or stop-loss.

    Only relevant if we have an open position in this symbol.
    """
    if not has_position:
        return 0.0, "no position"

    rsi = snap.get("rsi")
    mom_short = snap.get("momentum_short")
    mom_med = snap.get("momentum_medium")
    trend_dir = snap.get("trend_direction")
    ema_cross = snap.get("ema_crossover")

    confidence = 0.0
    reasons = []

    # Overbought → take profit
    if rsi is not None and rsi > 72:
        confidence += 0.4
        reasons.append(f"RSI overbought ({rsi:.0f})")

    # Momentum reversal
    if mom_short is not None and mom_short < -0.5:
        confidence += 0.2
        reasons.append(f"short momentum dropping ({mom_short:.2f}%)")

    if mom_med is not None and mom_med < -1.0:
        confidence += 0.15
        reasons.append(f"medium momentum negative ({mom_med:.2f}%)")

    # Trend breaking down
    if trend_dir is not None and trend_dir < -0.1:
        confidence += 0.1
        reasons.append("trend turning bearish")

    # EMA death cross
    if ema_cross is not None and ema_cross < -0.1:
        confidence += 0.15
        reasons.append(f"EMA crossover bearish ({ema_cross:.3f}%)")

    # ── Chart pattern sell boosts ──
    patterns = snap.get("patterns", [])
    mtf_alignment = snap.get("mtf_alignment")
    resistance_levels = snap.get("resistance_levels", [])
    current_price = snap.get("mid", 0)

    # Bearish reversal patterns boost sell
    bearish_patterns = [p for p in patterns if p.get("direction") == "bearish"]
    if bearish_patterns:
        best = max(bearish_patterns, key=lambda p: p.get("strength", 0))
        pattern_boost = min(0.15, best.get("strength", 0) * 0.18)
        confidence += pattern_boost
        reasons.append(f"bearish pattern: {best.get('name')} ({best.get('strength', 0):.0%})")

    # MTF bearish alignment boosts sell
    if mtf_alignment is not None and mtf_alignment < -0.5:
        confidence += 0.10
        reasons.append(f"MTF aligned bearish ({mtf_alignment:+.2f})")

    # At resistance — good time to take profit
    if current_price > 0 and resistance_levels:
        nearest = min(resistance_levels, key=lambda l: abs(l.get("price", 0) - current_price))
        dist_pct = abs(current_price - nearest.get("price", 0)) / current_price * 100
        if dist_pct < 1.0:
            confidence += 0.08
            reasons.append(f"at resistance ${nearest.get('price', 0):,.0f}")

    confidence = min(1.0, max(0.0, confidence))
    reason = "; ".join(reasons) if reasons else "no sell signal"
    return confidence, reason


def generate_signals(
    candidates: list[CandidateScan],
    price_cache: PriceCache,
    open_positions: set[str],
    max_notional: float = DEFAULT_SIGNAL_NOTIONAL,
    max_signals: int = 3,
) -> list[Signal]:
    """Produce ranked signals from scanner output.

    Args:
        candidates: Scored candidates from scan_candidates()
        price_cache: Price cache for technical snapshot
        open_positions: Set of symbols we currently hold
        max_notional: Max notional per signal
        max_signals: Maximum actionable signals to return

    Returns:
        List of Signal objects, sorted by confidence descending.
        Includes HOLD signals for context but they're not actionable.
    """
    signals: list[Signal] = []

    for cand in candidates:
        snap = price_cache.snapshot(cand.symbol)
        has_position = cand.symbol in open_positions

        # Merge chart analysis data from scanner info into snapshot
        # so signal functions can access patterns, MTF, S/R levels
        for chart_key in ("patterns", "mtf_alignment", "mtf_dominant_trend",
                          "support_levels", "resistance_levels"):
            if chart_key in cand.info:
                snap[chart_key] = cand.info[chart_key]

        indicators = {
            "rsi": snap.get("rsi"),
            "momentum_short": snap.get("momentum_short"),
            "momentum_medium": snap.get("momentum_medium"),
            "ema_crossover": snap.get("ema_crossover"),
            "volatility": snap.get("volatility"),
            "trend_strength": snap.get("trend_strength"),
            "trend_direction": snap.get("trend_direction"),
            "spread_pct": snap.get("spread_pct"),
            "mtf_alignment": snap.get("mtf_alignment"),
            "patterns": snap.get("patterns", []),
        }

        # Check for sell signal first (if we have a position)
        sell_conf, sell_reason = _compute_sell_confidence(cand, snap, has_position)
        if sell_conf >= MIN_CONFIDENCE_SELL:
            signals.append(Signal(
                symbol=cand.symbol,
                action="SELL",
                confidence=sell_conf,
                reason=sell_reason,
                strategy=cand.recommended_strategy,
                suggested_notional=max_notional,  # sell full position
                score=cand.score,
                indicators=indicators,
            ))
            continue

        # Check buy signal (only if we don't already hold)
        if not has_position:
            buy_conf, buy_reason = _compute_buy_confidence(cand, snap)

            if buy_conf >= MIN_CONFIDENCE_BUY:
                # Scale notional by confidence (more confident → bigger position)
                sized_notional = round(max_notional * min(1.0, buy_conf / 0.85), 2)
                signals.append(Signal(
                    symbol=cand.symbol,
                    action="BUY",
                    confidence=buy_conf,
                    reason=buy_reason,
                    strategy=cand.recommended_strategy,
                    suggested_notional=sized_notional,
                    score=cand.score,
                    indicators=indicators,
                ))
            else:
                # HOLD — not confident enough
                signals.append(Signal(
                    symbol=cand.symbol,
                    action="HOLD",
                    confidence=buy_conf,
                    reason=buy_reason or f"below threshold ({buy_conf:.2f} < {MIN_CONFIDENCE_BUY})",
                    strategy=cand.recommended_strategy,
                    suggested_notional=0,
                    score=cand.score,
                    indicators=indicators,
                ))
        else:
            # Have position but no sell signal → HOLD
            signals.append(Signal(
                symbol=cand.symbol,
                action="HOLD",
                confidence=0.0,
                reason="holding position — no sell trigger",
                strategy=cand.recommended_strategy,
                suggested_notional=0,
                score=cand.score,
                indicators=indicators,
            ))

    # Sort: actionable signals first (by confidence), then HOLDs
    signals.sort(key=lambda s: (s.is_actionable, s.confidence), reverse=True)

    # Limit actionable signals
    actionable_count = 0
    result = []
    for sig in signals:
        if sig.is_actionable:
            if actionable_count < max_signals:
                result.append(sig)
                actionable_count += 1
            else:
                # Downgrade to HOLD if we hit max
                sig = Signal(
                    symbol=sig.symbol, action="HOLD", confidence=sig.confidence,
                    reason=f"max signals ({max_signals}) reached",
                    strategy=sig.strategy, suggested_notional=0,
                    score=sig.score, indicators=sig.indicators,
                )
                result.append(sig)
        else:
            result.append(sig)

    return result
