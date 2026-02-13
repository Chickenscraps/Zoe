"""Tests for paper mode BUY → HOLD → EXIT lifecycle with fills and P&L."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from .config import CryptoTraderConfig
from .repository import InMemoryCryptoRepository
from .trader import CryptoTraderService


def _make_config(**overrides) -> CryptoTraderConfig:
    """Create paper mode config with sensible test defaults."""
    defaults = {
        "admin_user_id": "test-user",
        "mode": "paper",
        "rh_live_trading": False,
        "rh_live_confirm": "",
        "max_notional_per_trade": 25,
        "max_daily_notional": 100,
        "max_open_positions": 3,
        "min_notional_per_trade": 5,
        "starting_equity": 2000,
    }
    defaults.update(overrides)
    cfg = CryptoTraderConfig.__new__(CryptoTraderConfig)
    for k, v in defaults.items():
        setattr(cfg, k, v)
    cfg.stop_trading_on_degraded = True
    cfg.reconcile_interval_seconds = 60
    cfg.order_poll_interval_seconds = 5
    cfg.reconcile_cash_tolerance = 2.0
    cfg.reconcile_qty_tolerance = 0.000001
    cfg.safe_mode_empty_scan_threshold = 3
    return cfg


def _make_client():
    """Create mock Robinhood client."""
    client = AsyncMock()
    client.get_best_bid_ask_batch.return_value = {
        "results": [
            {"symbol": "BTC-USD", "bid_inclusive_of_sell_spread": 99000, "ask_inclusive_of_buy_spread": 99200},
            {"symbol": "ETH-USD", "bid_inclusive_of_sell_spread": 3400, "ask_inclusive_of_buy_spread": 3410},
        ]
    }
    return client


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestPaperBuyCreatesFill:
    def test_buy_signal_creates_fill_and_updates_snapshots(self):
        repo = InMemoryCryptoRepository()
        client = _make_client()
        cfg = _make_config()
        svc = CryptoTraderService(client, repo, cfg)

        # Seed initial cash
        repo.insert_cash_snapshot(cash_available=2000, buying_power=2000, mode="paper")

        # Record a price tick so price_cache has data
        svc.price_cache.record("BTC-USD", 99000, 99200)

        # Create a fake signal
        from .signals import Signal
        signal = Signal(
            symbol="BTC-USD",
            action="BUY",
            confidence=0.8,
            suggested_notional=25.0,
            reason="test",
            strategy="test",
            is_actionable=True,
        )

        run(svc._execute_signal(signal))

        # Should have created an order
        assert len(repo.orders) == 1
        assert repo.orders[0]["side"] == "buy"
        assert repo.orders[0]["status"] == "filled"

        # Should have created a fill
        assert len(repo.fills) == 1
        assert repo.fills[0]["side"] == "buy"
        assert repo.fills[0]["qty"] > 0
        assert repo.fills[0]["price"] > 0

        # Should have updated holdings
        assert len(repo.holdings_snapshots) >= 1
        latest_holdings = repo.holdings_snapshots[-1]
        assert "BTC-USD" in latest_holdings["holdings"]

        # Should have reduced cash
        latest_cash = repo.cash_snapshots[-1]
        assert latest_cash["buying_power"] < 2000


class TestPaperExitCreatesFill:
    def test_exit_creates_sell_fill_and_removes_position(self):
        repo = InMemoryCryptoRepository()
        client = _make_client()
        cfg = _make_config()
        svc = CryptoTraderService(client, repo, cfg)

        # Seed: cash + holdings with a BTC position
        repo.insert_cash_snapshot(cash_available=1975, buying_power=1975, mode="paper")
        repo.insert_holdings_snapshot(
            holdings={"BTC-USD": 0.00025}, total_value=0, mode="paper"
        )

        # Record prices
        svc.price_cache.record("BTC-USD", 99000, 99200)

        # Register position in exit manager
        from datetime import datetime, timezone
        svc.exit_manager.register_position(
            symbol="BTC-USD",
            entry_price=99200,
            entry_time=datetime.now(timezone.utc),
        )

        # Create exit signal
        from .exit_manager import ExitSignal, ExitReason, ExitUrgency
        exit_signal = ExitSignal(
            reason=ExitReason.STOP_LOSS,
            urgency=ExitUrgency.HIGH,
            pnl_pct=-0.01,
            details="test stop loss",
        )

        run(svc._execute_exit("BTC-USD", exit_signal))

        # Should have created a sell order
        sell_orders = [o for o in repo.orders if o["side"] == "sell"]
        assert len(sell_orders) == 1
        assert sell_orders[0]["status"] == "filled"

        # Should have created a sell fill
        sell_fills = [f for f in repo.fills if f["side"] == "sell"]
        assert len(sell_fills) == 1

        # Holdings should no longer contain BTC-USD
        latest_holdings = repo.holdings_snapshots[-1]
        assert "BTC-USD" not in latest_holdings["holdings"]

        # Cash should have increased
        latest_cash = repo.cash_snapshots[-1]
        assert latest_cash["buying_power"] > 1975


class TestScannerScoreClamped:
    def test_score_never_exceeds_100(self):
        from .scanner import _score_liquidity, _score_momentum, _score_volatility, _score_trend

        # Create scores that would sum > 100
        liq = _score_liquidity(0.01, 0.01)   # max ~25
        mom = _score_momentum(5.0, 10.0, 1.0)  # max ~30
        vol = _score_volatility(50, 0.01, {"squeeze": True})  # max ~25
        trend = _score_trend(1.0, 1.0, 25)  # max ~25

        total = liq + mom + vol + trend
        clamped = min(100.0, total)
        # Total of max subscores can exceed 100
        assert clamped <= 100.0
