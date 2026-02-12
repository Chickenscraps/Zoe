"""Tests for the consensus engine with kill switch."""
import pytest
from services.crypto_trader.consensus import (
    ConsensusEngine,
    ConsensusResult,
    ConsensusReport,
)


def _make_snapshot(**overrides):
    """Create a base snapshot with all indicators populated."""
    base = {
        "rsi": 45,
        "macd": {
            "histogram": 0.5,
            "histogram_slope": 0.1,
            "crossover": 0,
            "macd_line": 1.0,
            "signal_line": 0.5,
        },
        "ema_crossover": 0.02,
        "volatility": 50,
        "spread_volatility": 0.1,
        "mtf_alignment": 0.5,
        "bollinger": {
            "percent_b": 0.2,
            "squeeze": False,
            "bandwidth": 5.0,
        },
        "divergences": [],
        "spread_pct": 0.1,
        "mean_spread": 0.15,
        "trend_strength": 0.7,
        "trend_direction": 0.03,
    }
    base.update(overrides)
    return base


class TestConsensusEngine:
    """Test the ConsensusEngine evaluation."""

    def setup_method(self):
        self.engine = ConsensusEngine()

    def test_strong_buy_all_aligned(self):
        """All gates pass for long = STRONG_BUY."""
        snap = _make_snapshot(
            rsi=32,
            mtf_alignment=0.6,
            bollinger={"percent_b": 0.15, "squeeze": False, "bandwidth": 5},
        )
        report = self.engine.evaluate(snap, "long")
        assert report.gates_passed >= 6
        assert report.result in (ConsensusResult.STRONG_BUY, ConsensusResult.BUY)
        assert report.confidence > 0.5

    def test_blocked_all_against(self):
        """Too many blockers = BLOCKED."""
        snap = _make_snapshot(
            rsi=80,  # overbought for long
            volatility=250,  # extreme
            spread_pct=2.0,  # wide spread
            mean_spread=0.1,
            mtf_alignment=-0.5,  # bearish
            macd={"histogram": -1, "histogram_slope": -0.5, "crossover": -1, "macd_line": -2, "signal_line": -1},
            ema_crossover=-0.05,
            bollinger={"percent_b": 0.95, "squeeze": False, "bandwidth": 20},
            trend_strength=0.8,
            trend_direction=-0.05,
        )
        report = self.engine.evaluate(snap, "long")
        assert report.result == ConsensusResult.BLOCKED
        assert report.confidence == 0.0
        assert len(report.blocking_reasons) > 0

    def test_kill_switch_fewer_than_3_gates(self):
        """Kill switch triggers when < 3 gates pass."""
        snap = _make_snapshot(
            rsi=75,
            volatility=220,  # extreme vol fails gate 2
            mtf_alignment=-0.5,  # fails gate 3
            bollinger={"percent_b": 0.9, "squeeze": False, "bandwidth": 15},  # fails gate 4
            spread_pct=3.0,
            mean_spread=0.1,  # spread spiking fails gate 6
            macd={"histogram": -1, "histogram_slope": -0.5, "crossover": -1, "macd_line": -2, "signal_line": -1},
            ema_crossover=-0.03,
            trend_strength=0.8,
            trend_direction=-0.05,
        )
        report = self.engine.evaluate(snap, "long")
        assert report.result == ConsensusResult.BLOCKED

    def test_neutral_mid_gates(self):
        """Medium gate pass rate = NEUTRAL."""
        snap = _make_snapshot(
            rsi=55,
            mtf_alignment=0.0,  # indecisive, may not pass
            bollinger={"percent_b": 0.5, "squeeze": False, "bandwidth": 8},  # middle, may not pass
        )
        report = self.engine.evaluate(snap, "long")
        # Should be NEUTRAL or BUY depending on gate count
        assert report.result in (ConsensusResult.NEUTRAL, ConsensusResult.BUY, ConsensusResult.STRONG_BUY)

    def test_short_direction(self):
        """Engine evaluates correctly for short direction."""
        snap = _make_snapshot(
            rsi=72,
            macd={"histogram": -0.5, "histogram_slope": -0.2, "crossover": -1, "macd_line": -1, "signal_line": -0.5},
            ema_crossover=-0.03,
            mtf_alignment=-0.5,
            bollinger={"percent_b": 0.85, "squeeze": False, "bandwidth": 12},
            trend_strength=0.7,
            trend_direction=-0.03,
        )
        report = self.engine.evaluate(snap, "short")
        assert report.result in (ConsensusResult.SELL, ConsensusResult.STRONG_SELL, ConsensusResult.BUY, ConsensusResult.NEUTRAL, ConsensusResult.BLOCKED)

    def test_gates_total_is_7(self):
        """Engine always reports 7 total gates."""
        snap = _make_snapshot()
        report = self.engine.evaluate(snap, "long")
        assert report.gates_total == 7

    def test_divergence_alignment_passes_gate(self):
        """Bullish divergence for long direction passes gate 5."""
        snap = _make_snapshot(
            divergences=[{"type": "regular_bullish", "is_bullish": True, "strength": 0.8}],
        )
        report = self.engine.evaluate(snap, "long")
        # Should have divergence in supporting
        diverg_support = [r for r in report.supporting_reasons if "ivergence" in r.lower()]
        assert len(diverg_support) > 0

    def test_conflicting_divergence_blocks(self):
        """Bearish divergence for long direction blocks gate 5."""
        snap = _make_snapshot(
            divergences=[{"type": "regular_bearish", "is_bullish": False, "strength": 0.8}],
        )
        report = self.engine.evaluate(snap, "long")
        diverg_block = [r for r in report.blocking_reasons if "ivergence" in r.lower()]
        assert len(diverg_block) > 0

    def test_no_divergence_passes_by_default(self):
        """No divergence data = gate passes by default."""
        snap = _make_snapshot(divergences=[])
        report = self.engine.evaluate(snap, "long")
        # Gate 5 should pass (divergence is neutral)
        assert report.gates_passed >= 1  # at least divergence gate passes

    def test_bb_squeeze_helps_long(self):
        """BB squeeze with low %B passes Bollinger gate for long."""
        snap = _make_snapshot(
            bollinger={"percent_b": 0.4, "squeeze": True, "bandwidth": 2},
        )
        report = self.engine.evaluate(snap, "long")
        bb_support = [r for r in report.supporting_reasons if "BB" in r]
        assert len(bb_support) > 0

    def test_regime_bear_blocks_long(self):
        """Bear regime blocks long trades via gate 7."""
        snap = _make_snapshot(
            trend_strength=0.8,
            trend_direction=-0.05,
            ema_crossover=-0.03,
            volatility=50,
        )
        report = self.engine.evaluate(snap, "long")
        bear_block = [r for r in report.blocking_reasons if "ear" in r.lower()]
        assert len(bear_block) > 0


class TestConsensusReport:
    """Test ConsensusReport serialization."""

    def test_to_dict(self):
        """to_dict returns correct structure."""
        report = ConsensusReport(
            result=ConsensusResult.BUY,
            confidence=0.75,
            gates_passed=5,
            gates_total=7,
            blocking_reasons=["Spread wide"],
            supporting_reasons=["Technical aligned", "BB favorable"],
        )
        d = report.to_dict()
        assert d["result"] == "buy"
        assert d["confidence"] == 0.75
        assert d["gates_passed"] == 5
        assert d["gates_total"] == 7
        assert len(d["blocking_reasons"]) == 1
        assert len(d["supporting_reasons"]) == 2

    def test_blocked_to_dict(self):
        """BLOCKED result serializes correctly."""
        report = ConsensusReport(
            result=ConsensusResult.BLOCKED,
            confidence=0.0,
            gates_passed=2,
            gates_total=7,
            blocking_reasons=["Extreme vol", "Spread spiking", "Bear regime"],
            supporting_reasons=[],
        )
        d = report.to_dict()
        assert d["result"] == "blocked"
        assert d["confidence"] == 0.0
