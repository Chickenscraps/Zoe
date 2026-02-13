"""Multi-indicator consensus engine with kill switch.

Implements the "Consensus Engine" / "Kill Switch" framework from
quantitative research: a technical signal is only valid when multiple
independent validation gates agree.

7 Validation Gates:
    1. Technical Alignment — RSI + MACD + EMA all point the same direction
    2. Volatility Environment — not in extreme vol, spread stable
    3. Multi-Timeframe Agreement — higher timeframes confirm direction
    4. Bollinger Confirmation — BB position matches the trade thesis
    5. Divergence Validation — no conflicting divergence signals
    6. Liquidity Health — spread within norms, not spiking
    7. Regime Consistency — market regime supports the trade direction

Kill Switch triggers (result = BLOCKED):
    - Fewer than 3 gates passed
    - Critical blocker present (extreme vol + illiquidity + conflicting signals)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .regime import detect_regime


class ConsensusResult(Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    BLOCKED = "blocked"


@dataclass
class ConsensusReport:
    """Result of the consensus engine evaluation."""

    result: ConsensusResult
    confidence: float       # 0.0-1.0
    gates_passed: int
    gates_total: int
    blocking_reasons: list[str] = field(default_factory=list)
    supporting_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "confidence": round(self.confidence, 3),
            "gates_passed": self.gates_passed,
            "gates_total": self.gates_total,
            "blocking_reasons": self.blocking_reasons,
            "supporting_reasons": self.supporting_reasons,
        }


class ConsensusEngine:
    """Multi-factor validation engine for trade signals."""

    GATES_TOTAL = 7

    def evaluate(self, snapshot: dict[str, Any], direction: str = "long") -> ConsensusReport:
        """Evaluate multi-indicator consensus for a trade direction.

        Args:
            snapshot: Full indicator snapshot (from price_cache + chart data).
            direction: "long" or "short".

        Returns:
            ConsensusReport with result, confidence, and reasoning.
        """
        gates_passed = 0
        blocking: list[str] = []
        supporting: list[str] = []

        # Gate 1: Technical Alignment (RSI + MACD + EMA)
        tech_score = self._gate_technical_alignment(snapshot, direction)
        if tech_score >= 0.6:
            gates_passed += 1
            supporting.append(f"Indicators aligned ({tech_score:.0%})")
        elif tech_score < 0.3:
            blocking.append(f"Technical conflict ({tech_score:.0%})")

        # Gate 2: Volatility Environment
        vol_ok, vol_msg = self._gate_volatility(snapshot)
        if vol_ok:
            gates_passed += 1
            supporting.append(vol_msg)
        else:
            blocking.append(vol_msg)

        # Gate 3: Multi-Timeframe Agreement
        mtf = snapshot.get("mtf_alignment")
        if mtf is not None:
            aligned = (direction == "long" and mtf > 0.3) or (direction == "short" and mtf < -0.3)
            if aligned:
                gates_passed += 1
                supporting.append(f"MTF aligned ({mtf:+.2f})")
            elif abs(mtf) < 0.15:
                blocking.append(f"MTF indecisive ({mtf:+.2f})")

        # Gate 4: Bollinger Confirmation
        bb = snapshot.get("bollinger")
        if bb is not None:
            pct_b = bb.get("percent_b", 0.5)
            squeeze = bb.get("squeeze", False)
            if direction == "long":
                if pct_b < 0.3 or (squeeze and pct_b < 0.5):
                    gates_passed += 1
                    label = "squeeze" if squeeze else f"%B={pct_b:.2f}"
                    supporting.append(f"BB favorable for long ({label})")
                elif pct_b > 0.85:
                    blocking.append(f"BB overbought (%B={pct_b:.2f})")
            else:
                if pct_b > 0.7 or (squeeze and pct_b > 0.5):
                    gates_passed += 1
                    supporting.append(f"BB favorable for short (%B={pct_b:.2f})")
                elif pct_b < 0.15:
                    blocking.append(f"BB oversold (%B={pct_b:.2f})")

        # Gate 5: Divergence Check
        divergences = snapshot.get("divergences", [])
        if divergences:
            aligned_divs = [
                d for d in divergences
                if (direction == "long" and d.get("is_bullish"))
                or (direction == "short" and not d.get("is_bullish"))
            ]
            conflicting = [
                d for d in divergences
                if (direction == "long" and not d.get("is_bullish"))
                or (direction == "short" and d.get("is_bullish"))
            ]
            if aligned_divs and not conflicting:
                gates_passed += 1
                supporting.append(f"Divergence confirms ({aligned_divs[0].get('type')})")
            elif conflicting:
                blocking.append(f"Conflicting divergence ({conflicting[0].get('type')})")
        else:
            # No divergence is neutral — pass by default
            gates_passed += 1

        # Gate 6: Liquidity Health
        spread = snapshot.get("spread_pct", 0)
        mean_spread = snapshot.get("mean_spread")
        spread_vol = snapshot.get("spread_volatility")
        if mean_spread is not None and mean_spread > 0:
            spread_ratio = spread / mean_spread if mean_spread else 1
            if spread_ratio < 1.5:
                gates_passed += 1
                supporting.append(f"Liquidity healthy (spread ratio {spread_ratio:.1f}x)")
            else:
                blocking.append(f"Spread spiking ({spread_ratio:.1f}x normal)")
        elif spread < 0.5:
            gates_passed += 1
            supporting.append(f"Spread tight ({spread:.3f}%)")
        elif spread > 1.0:
            blocking.append(f"Spread wide ({spread:.3f}%)")

        # Gate 7: Regime Consistency
        regime = detect_regime(snapshot)
        if direction == "long":
            if regime.regime in ("bull", "sideways"):
                gates_passed += 1
                supporting.append(f"Regime supports long ({regime.regime})")
            elif regime.regime == "bear":
                blocking.append(f"Bear regime — risky for longs")
            elif regime.regime == "high_vol":
                # Not blocking but not supporting
                pass
        else:
            if regime.regime in ("bear", "sideways"):
                gates_passed += 1
                supporting.append(f"Regime supports short ({regime.regime})")
            elif regime.regime == "bull":
                blocking.append(f"Bull regime — risky for shorts")

        # ── Determine final result ──
        pass_rate = gates_passed / self.GATES_TOTAL
        critical_blockers = len(blocking) >= 2  # tightened from 3

        # Raised minimum from 3/7 to 5/7 — require strong consensus
        if critical_blockers or pass_rate < 5 / self.GATES_TOTAL:
            return ConsensusReport(
                result=ConsensusResult.BLOCKED,
                confidence=0.0,
                gates_passed=gates_passed,
                gates_total=self.GATES_TOTAL,
                blocking_reasons=blocking,
                supporting_reasons=supporting,
            )

        if pass_rate >= 6 / self.GATES_TOTAL:
            result = ConsensusResult.STRONG_BUY if direction == "long" else ConsensusResult.STRONG_SELL
            confidence = min(1.0, pass_rate * 1.1)
        elif pass_rate >= 5 / self.GATES_TOTAL:
            result = ConsensusResult.BUY if direction == "long" else ConsensusResult.SELL
            confidence = pass_rate
        else:
            result = ConsensusResult.NEUTRAL
            confidence = pass_rate * 0.5

        return ConsensusReport(
            result=result,
            confidence=round(confidence, 3),
            gates_passed=gates_passed,
            gates_total=self.GATES_TOTAL,
            blocking_reasons=blocking,
            supporting_reasons=supporting,
        )

    # ── Gate helpers ────────────────────────────────────────────

    def _gate_technical_alignment(
        self, snapshot: dict[str, Any], direction: str,
    ) -> float:
        """Check RSI + MACD + EMA alignment. Returns 0.0-1.0."""
        score = 0.0
        n_indicators = 0

        # RSI
        rsi = snapshot.get("rsi")
        if rsi is not None:
            n_indicators += 1
            if direction == "long":
                if rsi < 35:
                    score += 1.0
                elif rsi < 50:
                    score += 0.7
                elif rsi < 65:
                    score += 0.4
                else:
                    score += 0.1
            else:
                if rsi > 65:
                    score += 1.0
                elif rsi > 50:
                    score += 0.7
                elif rsi > 35:
                    score += 0.4
                else:
                    score += 0.1

        # MACD
        macd = snapshot.get("macd")
        if macd is not None and macd.get("histogram") is not None:
            n_indicators += 1
            hist = macd["histogram"]
            slope = macd.get("histogram_slope", 0)
            if direction == "long":
                if hist > 0 and slope > 0:
                    score += 1.0
                elif hist > 0:
                    score += 0.7
                elif slope > 0:
                    score += 0.4
                else:
                    score += 0.1
            else:
                if hist < 0 and slope < 0:
                    score += 1.0
                elif hist < 0:
                    score += 0.7
                elif slope < 0:
                    score += 0.4
                else:
                    score += 0.1

        # EMA crossover
        ema_cross = snapshot.get("ema_crossover")
        if ema_cross is not None:
            n_indicators += 1
            if direction == "long" and ema_cross > 0:
                score += min(1.0, ema_cross * 5)
            elif direction == "short" and ema_cross < 0:
                score += min(1.0, abs(ema_cross) * 5)
            else:
                score += 0.2

        return score / n_indicators if n_indicators > 0 else 0.5

    def _gate_volatility(self, snapshot: dict[str, Any]) -> tuple[bool, str]:
        """Check if volatility environment is acceptable for trading."""
        vol = snapshot.get("volatility")
        spread_vol = snapshot.get("spread_volatility")

        if vol is None:
            return True, "Volatility data unavailable (pass)"

        if vol > 200:
            return False, f"Extreme volatility ({vol:.0f}% ann.)"

        if spread_vol is not None and spread_vol > 0.5:
            return False, f"Erratic liquidity (spread vol {spread_vol:.2f})"

        return True, f"Volatility acceptable ({vol:.0f}%)"
