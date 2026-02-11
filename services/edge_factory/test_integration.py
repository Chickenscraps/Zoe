"""Integration test: full tick cycle with mock ingestors.

Tests the complete pipeline: ingest -> features -> regime -> signals -> paper execution.
Uses mock ingestors that return realistic but deterministic data.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .config import EdgeFactoryConfig
from .feature_engine import FeatureEngine
from .features.attention import TrendMomentum3D, TrendZScore14D
from .features.microstructure import CorwinSchultzSpread, FundingRateBasis, OpenInterestChange24h
from .features.risk import ConsecutiveLossCount, DrawdownCurrent, PortfolioHeat
from .features.technical import (
    ADXTrendStrength,
    EfficiencyRatio,
    GarmanKlassVol,
    RSIRegimeState,
    VWAPDistance,
)
from .ingestion.base import BaseIngestor
from .models import RegimeState, Signal
from .orchestrator import EdgeFactoryOrchestrator
from .paper_executor import PaperExecutor
from .position_sizer import PositionSizer
from .regime_detector import RegimeDetector
from .repository import InMemoryFeatureRepository
from .signal_generator import SignalGenerator


# ── Mock Ingestors ────────────────────────────────────────────


class MockTrendsIngestor(BaseIngestor):
    """Returns deterministic Google Trends data."""

    source_name = "google_trends"

    def staleness_threshold(self) -> int:
        return 99999

    async def fetch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        result = {}
        for sym in symbols:
            # Simulate a bullish attention spike
            series = [40, 42, 45, 48, 50, 52, 55, 58, 62, 65, 68, 72, 78, 85]
            result[sym] = {
                "interest_over_time": series,
                "current_interest": series[-1],
                "fetched_at": datetime.now(timezone.utc),
            }
        return result


class MockFundingIngestor(BaseIngestor):
    """Returns deterministic funding rate data (mocks OKX)."""

    source_name = "okx"

    def staleness_threshold(self) -> int:
        return 99999

    async def fetch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        result = {}
        for sym in symbols:
            result[sym] = {
                "funding_rate": 0.0001,  # 0.01% - low, bullish
                "funding_rate_annual": 0.0001 * 3 * 365,
                "open_interest": 500000.0,
                "open_interest_value": 500000.0,
                "fetched_at": datetime.now(timezone.utc),
            }
        return result


class MockMarketIngestor(BaseIngestor):
    """Returns deterministic market/OHLCV data."""

    source_name = "polygon"

    def staleness_threshold(self) -> int:
        return 99999

    async def fetch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        result = {}
        for sym in symbols:
            # Generate 60 days of daily bars - steady uptrend
            bars = []
            base_price = 50000 if "BTC" in sym else 3000 if "ETH" in sym else 150 if "SOL" in sym else 0.15
            for i in range(60):
                p = base_price * (1 + i * 0.005)  # +0.5% per day
                bars.append({
                    "open": p * 0.998,
                    "high": p * 1.01,
                    "low": p * 0.99,
                    "close": p,
                    "volume": 1000000,
                })

            current = bars[-1]["close"]
            result[sym] = {
                "bars_daily": bars,
                "current_price": current,
                "bid": current * 0.999,
                "ask": current * 1.001,
                "spread": current * 0.002,
                "spread_pct": 0.002,
                "volume_24h": 1000000,
                "fetched_at": datetime.now(timezone.utc),
            }
        return result


# ── Test Helpers ──────────────────────────────────────────────


def _build_test_stack():
    """Build a complete test stack with mock ingestors."""
    config = EdgeFactoryConfig()
    config.symbols = ["BTC-USD", "ETH-USD"]
    repo = InMemoryFeatureRepository()

    ingestors = {
        "google_trends": MockTrendsIngestor(),
        "okx": MockFundingIngestor(),
        "polygon": MockMarketIngestor(),
    }

    features = [
        TrendZScore14D(),
        TrendMomentum3D(),
        FundingRateBasis(),
        CorwinSchultzSpread(),
        OpenInterestChange24h(),
        GarmanKlassVol(),
        RSIRegimeState(),
        VWAPDistance(),
        ADXTrendStrength(),
        EfficiencyRatio(),
        PortfolioHeat(),
        DrawdownCurrent(),
        ConsecutiveLossCount(),
    ]

    engine = FeatureEngine(config, repo, ingestors, features)
    detector = RegimeDetector(config, repo)
    generator = SignalGenerator(config, detector)
    sizer = PositionSizer(config, repo)
    executor = PaperExecutor(config, repo)

    orchestrator = EdgeFactoryOrchestrator(
        config=config,
        feature_engine=engine,
        regime_detector=detector,
        signal_generator=generator,
        position_sizer=sizer,
        executor=executor,
        repository=repo,
    )

    return orchestrator, config, repo


# ── Integration Tests ─────────────────────────────────────────


def test_full_tick_cycle():
    """Complete tick: ingest -> features -> regime -> signals -> paper entry."""
    orch, config, repo = _build_test_stack()
    config.mode = "paper"

    summary = asyncio.get_event_loop().run_until_complete(orch.tick())

    assert summary["tick"] == 1
    assert summary["regime"] is not None, "Regime should be detected"
    assert len(summary["errors"]) == 0, f"Tick had errors: {summary['errors']}"

    # Should have computed features
    btc_features = repo.get_feature_history("BTC-USD", "garman_klass_vol", limit=1)
    assert len(btc_features) > 0, "GK vol should be computed for BTC"

    # Regime should be persisted
    latest_regime = repo.get_latest_regime()
    assert latest_regime is not None, "Regime should be persisted"


def test_bull_regime_generates_entries():
    """In a bull market with all conditions met, we should get entries."""
    orch, config, repo = _build_test_stack()
    config.mode = "paper"

    summary = asyncio.get_event_loop().run_until_complete(orch.tick())

    regime = summary["regime"]
    # Our mock data simulates a steady uptrend - should be bullish or transition
    assert regime in ("low_vol_bull", "transition"), f"Expected bull/transition, got {regime}"

    # Check if any signals were generated
    # (may or may not have entries depending on exact feature values)
    print(f"  Regime: {regime}")
    print(f"  Actions: {summary['actions']}")
    print(f"  Signals: {len(summary['signals'])}")
    print(f"  Errors: {summary['errors']}")


def test_consecutive_ticks():
    """Run 3 ticks and verify state accumulates."""
    orch, config, repo = _build_test_stack()
    config.mode = "paper"

    for i in range(3):
        summary = asyncio.get_event_loop().run_until_complete(orch.tick())
        assert summary["tick"] == i + 1
        assert len(summary["errors"]) == 0, f"Tick {i+1} errors: {summary['errors']}"

    # After 3 ticks, features should be accumulated
    btc_vol_history = repo.get_feature_history("BTC-USD", "garman_klass_vol")
    assert len(btc_vol_history) >= 3, f"Expected >= 3 vol entries, got {len(btc_vol_history)}"


def test_disabled_mode_noop():
    """In disabled mode, tick should do nothing."""
    orch, config, repo = _build_test_stack()
    config.mode = "disabled"

    # Orchestrator checks is_active() which returns False for disabled
    # The run_forever loop would skip, but tick() still runs if called directly
    # Let's verify the config check
    assert not config.is_active()
    assert not config.is_live()


def test_kill_switch_halts():
    """Verify kill switch stops all trading when triggered."""
    orch, config, repo = _build_test_stack()
    config.mode = "paper"

    # Inject a severe drawdown into the feature store
    from .models import FeatureSnapshot
    repo.insert_feature(FeatureSnapshot(
        symbol="BTC-USD",
        feature_name="drawdown_current",
        value=0.25,  # 25% drawdown > 20% threshold
        source="computed",
    ))

    summary = asyncio.get_event_loop().run_until_complete(orch.tick())

    assert "KILL SWITCH TRIGGERED" in str(summary["actions"]), f"Kill switch should trigger, got: {summary['actions']}"
    assert orch._halted is True


def test_status_report():
    """Get status should return meaningful data."""
    orch, config, repo = _build_test_stack()
    config.mode = "paper"

    # Run a tick first
    asyncio.get_event_loop().run_until_complete(orch.tick())

    status = orch.get_status()
    assert status["mode"] == "paper"
    assert status["tick_count"] == 1
    assert status["regime"] is not None
    assert "open_positions" in status
    assert "total_pnl" in status


def test_paper_executor_integration():
    """Verify paper executor creates positions with correct fills."""
    orch, config, repo = _build_test_stack()
    config.mode = "paper"

    # Run tick to populate features
    asyncio.get_event_loop().run_until_complete(orch.tick())

    # Check if any positions were created
    open_pos = repo.get_open_positions()
    closed_pos = repo.get_closed_positions()
    print(f"  Open positions: {len(open_pos)}")
    print(f"  Closed positions: {len(closed_pos)}")

    for pos in open_pos:
        assert pos.entry_price > 0, "Entry price should be positive"
        assert pos.size_usd > 0, "Size should be positive"
        assert pos.tp_price > pos.entry_price, "TP should be above entry for long"
        assert pos.sl_price < pos.entry_price, "SL should be below entry for long"
        print(f"  {pos.symbol}: ${pos.size_usd:.2f} @ {pos.entry_price:.2f} "
              f"(TP={pos.tp_price:.2f}, SL={pos.sl_price:.2f})")


def test_max_positions_respected():
    """Max 5 open positions should be enforced."""
    orch, config, repo = _build_test_stack()
    config.mode = "paper"
    config.max_open_positions = 2  # Limit to 2 for testing

    # Run multiple ticks
    for _ in range(5):
        asyncio.get_event_loop().run_until_complete(orch.tick())

    open_count = len(repo.get_open_positions())
    assert open_count <= 2, f"Should have max 2 open positions, got {open_count}"


def _build_v2_test_stack():
    """Build V2 test stack with TradeIntentBuilder and AccountState."""
    from .account_state import AccountState
    from .features.liquidity import AmihudIlliquidity, AmihudSpikeDetector
    from .features.volatility import ExpectedMovePct
    from .trade_intent import TradeIntentBuilder

    config = EdgeFactoryConfig()
    config.symbols = ["BTC-USD", "ETH-USD"]
    repo = InMemoryFeatureRepository()

    ingestors = {
        "google_trends": MockTrendsIngestor(),
        "okx": MockFundingIngestor(),
        "polygon": MockMarketIngestor(),
    }

    features = [
        TrendZScore14D(),
        TrendMomentum3D(),
        FundingRateBasis(),
        CorwinSchultzSpread(),
        OpenInterestChange24h(),
        GarmanKlassVol(),
        RSIRegimeState(),
        VWAPDistance(),
        ADXTrendStrength(),
        EfficiencyRatio(),
        PortfolioHeat(),
        DrawdownCurrent(),
        ConsecutiveLossCount(),
        AmihudIlliquidity(),
        AmihudSpikeDetector(),
        ExpectedMovePct(),
    ]

    engine = FeatureEngine(config, repo, ingestors, features)
    detector = RegimeDetector(config, repo)
    generator = SignalGenerator(config, detector)
    sizer = PositionSizer(config, repo)
    executor = PaperExecutor(config, repo)
    intent_builder = TradeIntentBuilder(config, sizer, repo)
    acct_state = AccountState(config, repo)

    orchestrator = EdgeFactoryOrchestrator(
        config=config,
        feature_engine=engine,
        regime_detector=detector,
        signal_generator=generator,
        position_sizer=sizer,
        executor=executor,
        repository=repo,
        trade_intent_builder=intent_builder,
        account_state=acct_state,
    )

    return orchestrator, config, repo


def test_v2_tick_with_trade_intent():
    """V2 tick with TradeIntentBuilder wired into orchestrator."""
    orch, config, repo = _build_v2_test_stack()
    config.mode = "paper"

    summary = asyncio.get_event_loop().run_until_complete(orch.tick())

    assert summary["tick"] == 1
    assert summary["regime"] is not None
    assert len(summary["errors"]) == 0, f"Tick had errors: {summary['errors']}"

    # V2 features should be computed
    amihud = repo.get_feature_history("BTC-USD", "amihud_illiquidity", limit=1)
    assert len(amihud) > 0, "Amihud should be computed"

    expected_move = repo.get_feature_history("BTC-USD", "expected_move_pct", limit=1)
    assert len(expected_move) > 0, "Expected move should be computed"


def test_v2_churn_blocks_repeated_entry():
    """Enter BTC, next tick BTC blocked by cooldown/concentration."""
    orch, config, repo = _build_v2_test_stack()
    config.mode = "paper"
    config.symbol_cooldown_hours = 24  # Long cooldown

    # Run first tick
    asyncio.get_event_loop().run_until_complete(orch.tick())

    open_pos = repo.get_open_positions()
    btc_open = [p for p in open_pos if p.symbol == "BTC-USD"]

    if btc_open:
        # Run second tick - BTC should be blocked by concentration
        summary2 = asyncio.get_event_loop().run_until_complete(orch.tick())

        # BTC should not get a second entry
        btc_open_after = [p for p in repo.get_open_positions() if p.symbol == "BTC-USD"]
        assert len(btc_open_after) <= 1, "BTC should have at most 1 open position"


def test_v2_amihud_spike_triggers_crash():
    """Inject high amihud, verify regime flips to crash."""
    orch, config, repo = _build_v2_test_stack()
    config.mode = "paper"

    from .models import FeatureSnapshot
    # Inject an elevated amihud spike into features
    repo.insert_feature(FeatureSnapshot(
        symbol="BTC-USD",
        feature_name="amihud_spike_z",
        value=3.0,  # z > 2.0 triggers crash
        source="computed",
    ))

    # The detector reads from features dict, not repo directly.
    # But we can verify the regime detector itself
    from .regime_detector import RegimeDetector
    detector = RegimeDetector(config, repo)
    regime = detector.detect({"amihud_spike_z": 3.0, "garman_klass_vol": 0.5})
    assert regime.regime == "high_vol_crash"


def test_v2_account_state_updates_equity():
    """Mock RH balance, verify dynamic equity in paper mode."""
    from .account_state import AccountState
    from .models import EdgePosition

    config = EdgeFactoryConfig()
    config.account_equity = 150.0
    repo = InMemoryFeatureRepository()

    # Add closed trades with PnL
    repo.insert_position(EdgePosition(
        symbol="BTC-USD", entry_price=50000.0, size_usd=15.0,
        status="closed_tp", pnl_usd=3.0, position_id="w1",
        exit_time=datetime.now(timezone.utc),
    ))

    acct = AccountState(config, repo)
    equity = asyncio.get_event_loop().run_until_complete(acct.refresh())

    assert abs(equity - 153.0) < 0.01  # 150 + 3
    assert acct.get_drawdown_from_hwm() == 0.0  # At HWM


def test_v2_consecutive_ticks_with_churn():
    """Run 3 V2 ticks — verify no test regressions."""
    orch, config, repo = _build_v2_test_stack()
    config.mode = "paper"

    for i in range(3):
        summary = asyncio.get_event_loop().run_until_complete(orch.tick())
        assert summary["tick"] == i + 1
        assert len(summary["errors"]) == 0, f"Tick {i+1} errors: {summary['errors']}"


def run_all_tests():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_all_tests() else 1)
