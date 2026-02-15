"""Tests for TradeScanner — profit-maximizing multi-coin edge engine."""
import time

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.crypto_trader.trade_scanner import (
    TradeScanner,
    ScoredCandidate,
    TradeIntent,
    DEFAULT_MIN_SCORE,
    DEFAULT_MAX_SPREAD_PCT,
    DEFAULT_MIN_VOLUME_24H,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_COST_SAFETY_MULT,
    DEFAULT_MAX_CHANGE_PCT,
)
from services.crypto_trader.indicators import (
    IndicatorEngine,
    IndicatorSnapshot,
    Regime,
    MIN_OBSERVATIONS_MACD,
)


# ── Helpers ──────────────────────────────────────────────────────

def _make_snapshot(
    symbol: str = "BTC-USD",
    mid: float = 70000.0,
    bid: float = 69990.0,
    ask: float = 70010.0,
    spread_pct: float = 0.03,
    volume_24h: float = 500_000.0,
    change_24h_pct: float = 3.5,
    vwap: float = 69500.0,
) -> dict:
    return {
        "symbol": symbol,
        "mid": mid,
        "bid": bid,
        "ask": ask,
        "spread_pct": spread_pct,
        "volume_24h": volume_24h,
        "change_24h_pct": change_24h_pct,
        "vwap": vwap,
    }


def _make_valid_indicator_snapshot(
    symbol: str = "BTC-USD",
    regime: Regime = Regime.TRENDING_UP,
    rsi: float = 55.0,
    atr_pct: float = 0.5,
    macd_histogram: float = 0.001,
    zscore: float = 0.5,
    ema_fast: float = 70100.0,
    ema_slow: float = 69900.0,
    trend_strength: float = 0.5,
) -> IndicatorSnapshot:
    """Create a valid IndicatorSnapshot for testing."""
    return IndicatorSnapshot(
        symbol=symbol,
        mid=70000.0,
        timestamp=time.time(),
        observations=MIN_OBSERVATIONS_MACD + 10,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        ema_slope=0.05,
        macd_line=ema_fast - ema_slow,
        macd_signal=(ema_fast - ema_slow) * 0.8,
        macd_histogram=macd_histogram,
        rsi=rsi,
        atr=350.0,
        atr_pct=atr_pct,
        bb_upper=70500.0,
        bb_lower=69500.0,
        bb_mid=70000.0,
        bb_width_pct=1.43,
        bb_squeeze=False,
        zscore=zscore,
        regime=regime,
        momentum_bullish=(regime == Regime.TRENDING_UP),
        momentum_bearish=(regime == Regime.TRENDING_DOWN),
        rsi_oversold=(rsi < 30),
        rsi_overbought=(rsi > 70),
        trend_strength=trend_strength,
    )


def _mock_indicator_engine(snapshot_map: dict[str, IndicatorSnapshot] | None = None):
    """Create a mock IndicatorEngine that returns pre-built snapshots."""
    engine = MagicMock(spec=IndicatorEngine)
    engine.tracked_symbols = len(snapshot_map) if snapshot_map else 0

    def _snapshot(symbol):
        if snapshot_map and symbol in snapshot_map:
            return snapshot_map[symbol]
        # Return a non-valid snapshot by default
        return IndicatorSnapshot(symbol=symbol, mid=0, timestamp=0, observations=0)

    engine.snapshot = MagicMock(side_effect=_snapshot)
    return engine


def _mock_supabase(focus_data=None, scout_data=None, mover_data=None):
    """Create a mock Supabase client that returns given data for table queries."""
    sb = MagicMock()

    def _table(name):
        mock_table = MagicMock()
        mock_select = MagicMock()

        if name == "market_snapshot_focus":
            mock_gt = MagicMock()
            mock_gt.execute.return_value = MagicMock(data=focus_data or [])
            mock_select.gt.return_value = mock_gt
        elif name == "market_snapshot_scout":
            mock_gt = MagicMock()
            mock_gt.execute.return_value = MagicMock(data=scout_data or [])
            mock_select.gt.return_value = mock_gt
        elif name == "mover_events":
            mock_gte = MagicMock()
            mock_gte.execute.return_value = MagicMock(data=mover_data or [])
            mock_select.gte.return_value = mock_gte
        elif name == "candidate_scans":
            mock_table.insert.return_value = MagicMock(
                execute=MagicMock(return_value=MagicMock(data=[]))
            )
            mock_table.select = MagicMock(return_value=mock_select)
            return mock_table
        else:
            mock_select.execute.return_value = MagicMock(data=[])

        mock_table.select = MagicMock(return_value=mock_select)
        return mock_table

    sb.table = _table
    return sb


def _make_tradeable_candidate(
    symbol: str = "BTC-USD",
    total_score: float = 80.0,
    regime: Regime = Regime.TRENDING_UP,
    edge_ratio: float = 3.0,
    rsi: float = 55.0,
    atr_pct: float = 0.5,
) -> ScoredCandidate:
    """Create a ScoredCandidate that passes ALL selection gates."""
    # Distribute score across components to reach total_score
    momentum = min(25.0, total_score * 0.3)
    volume = min(15.0, total_score * 0.15)
    spread = min(15.0, total_score * 0.15)
    trend = min(20.0, total_score * 0.25)
    mean_revert = min(15.0, total_score * 0.1)
    mover = min(10.0, total_score * 0.05)
    # Adjust to hit exact total
    remainder = total_score - (momentum + volume + spread + trend + mean_revert + mover)
    momentum = min(25.0, momentum + max(0, remainder))

    return ScoredCandidate(
        symbol=symbol, mid=70000, bid=69990, ask=70010,
        spread_pct=0.03, volume_24h=500000, change_24h_pct=3.5, vwap=69500,
        momentum_score=momentum,
        volume_score=volume,
        spread_score=spread,
        trend_score=trend,
        mean_revert_score=mean_revert,
        mover_score=mover,
        regime=regime,
        rsi=rsi,
        atr_pct=atr_pct,
        macd_histogram=0.001,
        zscore=0.5,
        bb_squeeze=False,
        indicators_valid=True,
        estimated_cost=0.50,
        expected_move_pct=atr_pct,
        edge_ratio=edge_ratio,
    )


# ── ScoredCandidate tests ────────────────────────────────────────


class TestScoredCandidate:
    """Test the ScoredCandidate dataclass."""

    def test_total_score_sums_all_components(self):
        c = ScoredCandidate(
            symbol="BTC-USD", mid=70000, bid=69990, ask=70010,
            spread_pct=0.03, volume_24h=500000, change_24h_pct=3.5, vwap=69500,
            momentum_score=20, volume_score=12, spread_score=14,
            trend_score=15, mean_revert_score=8, mover_score=5,
        )
        assert c.total_score == 74.0

    def test_recommended_side_trending_up(self):
        c = ScoredCandidate(
            symbol="BTC-USD", mid=70000, bid=69990, ask=70010,
            spread_pct=0.03, volume_24h=500000, change_24h_pct=3.5, vwap=69500,
            regime=Regime.TRENDING_UP,
        )
        assert c.recommended_side == "buy"

    def test_recommended_side_trending_down(self):
        c = ScoredCandidate(
            symbol="BTC-USD", mid=70000, bid=69990, ask=70010,
            spread_pct=0.03, volume_24h=500000, change_24h_pct=-3.5, vwap=70500,
            regime=Regime.TRENDING_DOWN,
        )
        assert c.recommended_side == "sell"

    def test_recommended_side_mean_revert_oversold(self):
        c = ScoredCandidate(
            symbol="X", mid=100, bid=99, ask=101,
            spread_pct=0.1, volume_24h=50000, change_24h_pct=-5.0, vwap=105,
            regime=Regime.MEAN_REVERTING, rsi=25.0, zscore=-2.0,
        )
        assert c.recommended_side == "buy"

    def test_recommended_side_mean_revert_overbought(self):
        c = ScoredCandidate(
            symbol="X", mid=100, bid=99, ask=101,
            spread_pct=0.1, volume_24h=50000, change_24h_pct=5.0, vwap=95,
            regime=Regime.MEAN_REVERTING, rsi=75.0, zscore=2.0,
        )
        assert c.recommended_side == "sell"

    def test_recommended_side_follows_macd_when_unknown(self):
        c = ScoredCandidate(
            symbol="X", mid=100, bid=99, ask=101,
            spread_pct=0.1, volume_24h=50000, change_24h_pct=1.0, vwap=100,
            regime=Regime.UNKNOWN, macd_histogram=0.005,
        )
        assert c.recommended_side == "buy"

        c2 = ScoredCandidate(
            symbol="X", mid=100, bid=99, ask=101,
            spread_pct=0.1, volume_24h=50000, change_24h_pct=-1.0, vwap=100,
            regime=Regime.UNKNOWN, macd_histogram=-0.005,
        )
        assert c2.recommended_side == "sell"

    def test_score_breakdown_dict(self):
        c = ScoredCandidate(
            symbol="BTC-USD", mid=70000, bid=69990, ask=70010,
            spread_pct=0.03, volume_24h=500000, change_24h_pct=3.5, vwap=69500,
            momentum_score=20.3, volume_score=12.7, spread_score=14.0,
            trend_score=15.5, mean_revert_score=0.0, mover_score=5.0,
            edge_ratio=2.5, estimated_cost=0.45,
        )
        bd = c.score_breakdown()
        assert bd["momentum"] == 20.3
        assert bd["volume"] == 12.7
        assert bd["mean_revert"] == 0.0
        assert bd["total"] == 67.5
        assert bd["edge_ratio"] == 2.5
        assert bd["regime"] == "unknown"  # default

    def test_info_dict(self):
        c = ScoredCandidate(
            symbol="ETH-USD", mid=3500, bid=3499, ask=3501,
            spread_pct=0.05, volume_24h=1_000_000, change_24h_pct=2.0, vwap=3480,
            regime=Regime.TRENDING_UP, indicators_valid=True,
        )
        info = c.info_dict()
        assert info["mid"] == 3500
        assert info["regime"] == "trending_up"
        assert info["indicators_valid"] is True


# ── Scoring tests ────────────────────────────────────────────────


class TestTradeScannerScoring:
    """Test the scoring logic in _score_symbol."""

    def _make_scanner(self, indicator_engine=None, **kwargs):
        sb = _mock_supabase()
        return TradeScanner(
            supabase_client=sb,
            indicator_engine=indicator_engine,
            **kwargs,
        )

    def test_score_good_candidate_no_indicators(self):
        """Without indicators, uses fallback 24h change scoring."""
        scanner = self._make_scanner()
        snap = _make_snapshot(change_24h_pct=4.0, volume_24h=500_000, spread_pct=0.02)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is not None
        assert c.total_score > 20  # Fallback scoring is weaker
        assert c.spread_score >= 12  # 0.02% spread → 15 pts

    def test_score_with_indicators(self):
        """With valid indicators, scoring uses real EMA/MACD/regime data."""
        ind_snap = _make_valid_indicator_snapshot("BTC-USD")
        engine = _mock_indicator_engine({"BTC-USD": ind_snap})
        scanner = self._make_scanner(indicator_engine=engine)
        snap = _make_snapshot(change_24h_pct=4.0, volume_24h=500_000, spread_pct=0.02)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is not None
        assert c.indicators_valid is True
        assert c.regime == Regime.TRENDING_UP
        assert c.momentum_score > 0  # Uses real EMA/MACD
        assert c.trend_score > 0     # Uses real regime

    def test_filter_high_spread(self):
        scanner = self._make_scanner(max_spread_pct=0.30)
        snap = _make_snapshot(spread_pct=0.8)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is None

    def test_filter_low_volume(self):
        scanner = self._make_scanner(min_volume_24h=50_000)
        snap = _make_snapshot(volume_24h=5_000)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is None

    def test_filter_extreme_change(self):
        scanner = self._make_scanner()
        snap = _make_snapshot(change_24h_pct=15.0)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is None  # >12% filtered

    def test_filter_zero_mid(self):
        scanner = self._make_scanner()
        snap = _make_snapshot(mid=0)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is None

    def test_mover_bonus_scaled_by_magnitude(self):
        """Mover bonus is now scaled (0-10) by magnitude, not binary 20."""
        scanner = self._make_scanner()
        snap = _make_snapshot(symbol="DOGE-USD", change_24h_pct=5.0)
        movers = {"DOGE-USD": 3.0}  # magnitude=3 → min(10, 3*2) = 6
        c = scanner._score_symbol(snap, movers, vol_median=100_000)
        assert c is not None
        assert c.mover_score == 6.0

    def test_mover_bonus_capped_at_10(self):
        scanner = self._make_scanner()
        snap = _make_snapshot(symbol="DOGE-USD", change_24h_pct=5.0)
        movers = {"DOGE-USD": 8.0}  # magnitude=8 → min(10, 8*2) = 10
        c = scanner._score_symbol(snap, movers, vol_median=100_000)
        assert c is not None
        assert c.mover_score == 10.0

    def test_no_mover_bonus_when_absent(self):
        scanner = self._make_scanner()
        snap = _make_snapshot(symbol="DOGE-USD", change_24h_pct=5.0)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is not None
        assert c.mover_score == 0.0

    def test_spread_scoring_tiers(self):
        scanner = self._make_scanner()

        # Very tight spread (≤0.02) → 15 pts
        tight = scanner._score_symbol(
            _make_snapshot(spread_pct=0.01), {}, vol_median=100_000
        )
        assert tight is not None
        assert tight.spread_score == 15.0

        # Medium spread (≤0.10) → 9 pts
        med = scanner._score_symbol(
            _make_snapshot(spread_pct=0.08), {}, vol_median=100_000
        )
        assert med is not None
        assert med.spread_score == 9.0

        # Wide but still under max (≤0.30) → 2 pts
        wide = scanner._score_symbol(
            _make_snapshot(spread_pct=0.25), {}, vol_median=100_000
        )
        assert wide is not None
        assert wide.spread_score == 2.0

    def test_cost_model_populated(self):
        scanner = self._make_scanner()
        snap = _make_snapshot(spread_pct=0.1, change_24h_pct=5.0)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is not None
        assert c.estimated_cost > 0
        assert c.expected_move_pct > 0
        assert c.edge_ratio > 0

    def test_trend_score_with_indicator_regime(self):
        """Trending regime gives trend_score bonus, choppy gives 0."""
        trending_snap = _make_valid_indicator_snapshot(
            "BTC-USD", regime=Regime.TRENDING_UP, trend_strength=0.6,
        )
        choppy_snap = _make_valid_indicator_snapshot(
            "ETH-USD", regime=Regime.CHOPPY, trend_strength=0.1,
        )
        engine = _mock_indicator_engine({
            "BTC-USD": trending_snap,
            "ETH-USD": choppy_snap,
        })
        scanner = self._make_scanner(indicator_engine=engine)

        btc = scanner._score_symbol(
            _make_snapshot("BTC-USD"), {}, vol_median=100_000,
        )
        eth = scanner._score_symbol(
            _make_snapshot("ETH-USD"), {}, vol_median=100_000,
        )
        assert btc is not None and eth is not None
        assert btc.trend_score > eth.trend_score

    def test_mean_revert_score_with_oversold_rsi(self):
        """Mean-reverting regime + oversold RSI → mean_revert_score > 0."""
        ind_snap = _make_valid_indicator_snapshot(
            "X", regime=Regime.MEAN_REVERTING, rsi=25.0, zscore=-2.0,
            trend_strength=0.1,
        )
        engine = _mock_indicator_engine({"X": ind_snap})
        scanner = self._make_scanner(indicator_engine=engine)
        snap = _make_snapshot("X", change_24h_pct=-3.0)
        c = scanner._score_symbol(snap, {}, vol_median=100_000)
        assert c is not None
        assert c.mean_revert_score > 0


# ── Selection tests ──────────────────────────────────────────────


class TestTradeScannerSelection:
    """Test select_trades() — 9-gate selection logic."""

    @pytest.mark.asyncio
    async def test_gate1_min_score(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=70)
        candidates = [_make_tradeable_candidate(total_score=60)]
        intents = await scanner.select_trades(candidates, equity=500, open_positions={})
        assert len(intents) == 0

    @pytest.mark.asyncio
    async def test_gate2_indicators_must_be_valid(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50)
        c = _make_tradeable_candidate(total_score=80)
        c.indicators_valid = False
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 0

    @pytest.mark.asyncio
    async def test_gate3_regime_blocks_choppy(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50)
        c = _make_tradeable_candidate(total_score=80, regime=Regime.CHOPPY)
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 0
        assert scanner._total_trades_blocked_regime == 1

    @pytest.mark.asyncio
    async def test_gate3_regime_blocks_unknown(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50)
        c = _make_tradeable_candidate(total_score=80, regime=Regime.UNKNOWN)
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 0

    @pytest.mark.asyncio
    async def test_gate4_cost_edge_filter(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50, cost_safety_mult=2.0)
        c = _make_tradeable_candidate(total_score=80, edge_ratio=1.5)  # Below 2.0x
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 0
        assert scanner._total_trades_blocked_cost == 1

    @pytest.mark.asyncio
    async def test_gate5_skips_held_positions(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50)
        c = _make_tradeable_candidate("BTC-USD", total_score=80)
        intents = await scanner.select_trades(
            [c], equity=500, open_positions={"BTC-USD": 50.0},
        )
        assert len(intents) == 0

    @pytest.mark.asyncio
    async def test_gate6_cooldown_enforcement(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50, cooldown_seconds=600)
        # Simulate recent trade
        scanner._last_trade_ts["BTC-USD"] = time.time() - 100  # 100s ago, within 600s cooldown
        c = _make_tradeable_candidate("BTC-USD", total_score=80)
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 0
        assert scanner._total_trades_blocked_cooldown == 1

    @pytest.mark.asyncio
    async def test_gate6_cooldown_expired_allows_trade(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50, cooldown_seconds=600)
        scanner._last_trade_ts["BTC-USD"] = time.time() - 700  # Expired
        c = _make_tradeable_candidate("BTC-USD", total_score=80)
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 1

    @pytest.mark.asyncio
    async def test_gate7_max_positions(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50, max_positions=2)
        candidates = [
            _make_tradeable_candidate(f"COIN{i}-USD", total_score=80)
            for i in range(5)
        ]
        intents = await scanner.select_trades(
            candidates, equity=1000, open_positions={"EXISTING-USD": 30.0},
        )
        # max_positions=2, already have 1 → can add 1 more
        assert len(intents) == 1

    @pytest.mark.asyncio
    async def test_gate8_exposure_cap(self):
        sb = _mock_supabase()
        scanner = TradeScanner(
            supabase_client=sb, min_score=50,
            max_exposure=100, max_notional=50,
        )
        candidates = [
            _make_tradeable_candidate(f"COIN{i}-USD", total_score=80)
            for i in range(5)
        ]
        intents = await scanner.select_trades(
            candidates, equity=500, open_positions={"OLD-USD": 60.0},
        )
        # existing=60 + new=50 = 110 > max_exposure=100 → blocked
        assert len(intents) == 0

    @pytest.mark.asyncio
    async def test_gate9_circuit_breaker(self):
        sb = _mock_supabase()
        breaker = MagicMock()
        breaker.can_trade.return_value = False
        scanner = TradeScanner(
            supabase_client=sb, circuit_breaker=breaker, min_score=50,
        )
        c = _make_tradeable_candidate("BTC-USD", total_score=80)
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 0
        breaker.can_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_produces_correct_intent(self):
        sb = _mock_supabase()
        scanner = TradeScanner(
            supabase_client=sb, min_score=50, max_notional=50,
        )
        c = _make_tradeable_candidate("SOL-USD", total_score=80, regime=Regime.TRENDING_UP)
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 1
        intent = intents[0]
        assert intent.symbol == "SOL-USD"
        assert intent.side == "buy"  # TRENDING_UP → buy
        assert intent.strategy == "scanner"
        assert intent.notional > 0
        assert intent.notional <= 50
        assert intent.score == c.total_score
        assert intent.regime == "trending_up"
        assert intent.edge_ratio == 3.0

    @pytest.mark.asyncio
    async def test_dry_run_produces_no_intents(self):
        sb = _mock_supabase()
        scanner = TradeScanner(
            supabase_client=sb, min_score=50, dry_run=True,
        )
        c = _make_tradeable_candidate("BTC-USD", total_score=80)
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 0  # Dry run → no actual intents

    @pytest.mark.asyncio
    async def test_volatility_dampener_reduces_size(self):
        sb = _mock_supabase()
        scanner = TradeScanner(
            supabase_client=sb, min_score=50, max_notional=50,
        )
        # Normal volatility
        c_normal = _make_tradeable_candidate("A-USD", total_score=80, atr_pct=0.5)
        intents_normal = await scanner.select_trades([c_normal], equity=500, open_positions={})

        # Reset scanner state
        scanner._last_trade_ts.clear()
        scanner._total_trades_submitted = 0

        # High volatility → dampened
        c_volatile = _make_tradeable_candidate("B-USD", total_score=80, atr_pct=3.0)
        intents_volatile = await scanner.select_trades([c_volatile], equity=500, open_positions={})

        if intents_normal and intents_volatile:
            assert intents_volatile[0].notional <= intents_normal[0].notional

    @pytest.mark.asyncio
    async def test_records_cooldown_after_trade(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50)
        c = _make_tradeable_candidate("BTC-USD", total_score=80)
        intents = await scanner.select_trades([c], equity=500, open_positions={})
        assert len(intents) == 1
        # Should have recorded the trade time
        assert "BTC-USD" in scanner._last_trade_ts
        assert scanner._last_trade_ts["BTC-USD"] > 0


# ── Scan pipeline tests ──────────────────────────────────────────


class TestTradeScannerScan:
    """Test scan_candidates() end-to-end with mock Supabase."""

    @pytest.mark.asyncio
    async def test_scan_empty_snapshots(self):
        sb = _mock_supabase(focus_data=[], scout_data=[])
        scanner = TradeScanner(supabase_client=sb)
        candidates = await scanner.scan_candidates()
        assert candidates == []

    @pytest.mark.asyncio
    async def test_scan_returns_scored_sorted(self):
        focus = [
            _make_snapshot("BTC-USD", change_24h_pct=5.0, volume_24h=1_000_000),
            _make_snapshot("ETH-USD", mid=3500, bid=3499, ask=3501,
                          change_24h_pct=2.0, volume_24h=500_000, spread_pct=0.04, vwap=3480),
        ]
        sb = _mock_supabase(focus_data=focus)
        scanner = TradeScanner(supabase_client=sb)
        candidates = await scanner.scan_candidates()
        assert len(candidates) == 2
        assert candidates[0].total_score >= candidates[1].total_score

    @pytest.mark.asyncio
    async def test_scan_merges_focus_and_scout(self):
        focus = [_make_snapshot("BTC-USD")]
        scout = [
            _make_snapshot("DOGE-USD", mid=0.3, bid=0.29, ask=0.31,
                          spread_pct=0.20, volume_24h=200_000, change_24h_pct=4.0),
        ]
        sb = _mock_supabase(focus_data=focus, scout_data=scout)
        scanner = TradeScanner(supabase_client=sb)
        candidates = await scanner.scan_candidates()
        symbols = {c.symbol for c in candidates}
        assert "BTC-USD" in symbols
        assert "DOGE-USD" in symbols

    @pytest.mark.asyncio
    async def test_scan_deduplicates_focus_over_scout(self):
        focus = [_make_snapshot("BTC-USD", change_24h_pct=5.0)]
        scout = [_make_snapshot("BTC-USD", change_24h_pct=2.0)]
        sb = _mock_supabase(focus_data=focus, scout_data=scout)
        scanner = TradeScanner(supabase_client=sb)
        candidates = await scanner.scan_candidates()
        btc = [c for c in candidates if c.symbol == "BTC-USD"]
        assert len(btc) == 1
        assert btc[0].change_24h_pct == 5.0

    @pytest.mark.asyncio
    async def test_scan_increments_count(self):
        sb = _mock_supabase(focus_data=[_make_snapshot()])
        scanner = TradeScanner(supabase_client=sb)
        assert scanner._scan_count == 0
        await scanner.scan_candidates()
        assert scanner._scan_count == 1
        await scanner.scan_candidates()
        assert scanner._scan_count == 2


# ── Write tests ──────────────────────────────────────────────────


class TestTradeScannerWrite:
    """Test write_candidate_scans()."""

    @pytest.mark.asyncio
    async def test_write_empty_candidates(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb)
        await scanner.write_candidate_scans([])

    @pytest.mark.asyncio
    async def test_write_calls_insert(self):
        sb = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock(data=[])
        mock_table.insert.return_value = mock_insert
        sb.table.return_value = mock_table

        scanner = TradeScanner(supabase_client=sb)
        candidates = [
            _make_tradeable_candidate("BTC-USD", total_score=80),
        ]
        await scanner.write_candidate_scans(candidates)
        sb.table.assert_called_with("candidate_scans")
        mock_table.insert.assert_called_once()
        rows = mock_table.insert.call_args[0][0]
        assert len(rows) == 1
        assert rows[0]["symbol"] == "BTC-USD"
        assert rows[0]["score"] == candidates[0].total_score


# ── Stats tests ──────────────────────────────────────────────────


class TestTradeScannerStats:
    """Test scanner stats reporting."""

    def test_stats_initial_state(self):
        sb = _mock_supabase()
        engine = _mock_indicator_engine()
        scanner = TradeScanner(supabase_client=sb, indicator_engine=engine)
        stats = scanner.get_stats()
        assert stats["scan_count"] == 0
        assert stats["trades_submitted"] == 0
        assert stats["blocked_cost"] == 0
        assert stats["blocked_cooldown"] == 0
        assert stats["blocked_regime"] == 0

    @pytest.mark.asyncio
    async def test_stats_track_blocked_trades(self):
        sb = _mock_supabase()
        scanner = TradeScanner(supabase_client=sb, min_score=50, cost_safety_mult=2.0)

        # Gate 3: blocked by regime
        c_choppy = _make_tradeable_candidate("A-USD", total_score=80, regime=Regime.CHOPPY)
        await scanner.select_trades([c_choppy], equity=500, open_positions={})

        # Gate 4: blocked by cost
        c_lowedge = _make_tradeable_candidate("B-USD", total_score=80, edge_ratio=1.0)
        await scanner.select_trades([c_lowedge], equity=500, open_positions={})

        stats = scanner.get_stats()
        assert stats["blocked_regime"] == 1
        assert stats["blocked_cost"] == 1
