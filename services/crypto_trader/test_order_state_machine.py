"""Tests for OrderManager state machine transitions and idempotency."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from .order_manager import OrderManager, ManagedOrder, TERMINAL_STATES, OPEN_STATES
from .reposition_policy import RepositionPolicy, RepositionDecision


class FakeBroker:
    """Fake broker for testing."""
    def __init__(self):
        self._orders = {}
        self._next_status = "submitted"

    async def place_order(self, **kwargs):
        oid = f"fake-{len(self._orders)}"
        self._orders[oid] = {"id": oid, "status": self._next_status, **kwargs}
        return self._orders[oid]

    async def cancel_order(self, order_id):
        if order_id in self._orders:
            self._orders[order_id]["status"] = "canceled"
        return self._orders.get(order_id, {})

    async def get_order(self, order_id):
        return self._orders.get(order_id, {"status": "not_found"})


class FakeRepo:
    """Fake repository for testing."""
    def __init__(self):
        self.orders = []
        self.fills = []
        self.status_updates = []

    def insert_order(self, order):
        self.orders.append(order)

    def update_order_status(self, order_id, status, raw):
        self.status_updates.append((order_id, status, raw))

    def list_open_orders(self, mode):
        return [o for o in self.orders if o.get("status") in ("submitted", "partially_filled", "working")]

    def upsert_fill(self, fill):
        self.fills.append(fill)


@pytest.fixture
def broker():
    return FakeBroker()


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def mgr(broker, repo):
    return OrderManager(broker=broker, repo=repo, mode="paper")


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestSubmitIntent:
    def test_creates_intent_and_order(self, mgr, repo):
        intent_id = run(mgr.submit_intent(symbol="BTC-USD", side="buy", notional=25.0))
        assert intent_id
        assert len(repo.orders) == 1
        assert repo.orders[0]["symbol"] == "BTC-USD"
        assert repo.orders[0]["intent_group_id"] == intent_id

    def test_order_tracked_in_memory(self, mgr):
        intent_id = run(mgr.submit_intent(symbol="ETH-USD", side="buy", notional=20.0))
        assert len(mgr._orders) == 1
        managed = list(mgr._orders.values())[0]
        assert managed.intent_group_id == intent_id
        assert managed.side == "buy"
        assert managed.replace_count == 0


class TestPollAndManage:
    def test_detects_fill_and_removes_from_tracking(self, mgr, broker):
        intent_id = run(mgr.submit_intent(symbol="BTC-USD", side="buy", notional=25.0))
        oid = list(mgr._orders.keys())[0]
        # Simulate broker filling the order
        broker._orders[oid]["status"] = "filled"
        run(mgr.poll_and_manage())
        assert len(mgr._orders) == 0

    def test_detects_rejection(self, mgr, broker):
        run(mgr.submit_intent(symbol="SOL-USD", side="buy", notional=10.0))
        oid = list(mgr._orders.keys())[0]
        broker._orders[oid]["status"] = "rejected"
        run(mgr.poll_and_manage())
        assert len(mgr._orders) == 0


class TestCancelOrder:
    def test_cancel_removes_from_tracking(self, mgr):
        run(mgr.submit_intent(symbol="BTC-USD", side="buy", notional=25.0))
        oid = list(mgr._orders.keys())[0]
        run(mgr.cancel_order(oid, reason="test"))
        assert len(mgr._orders) == 0


class TestPendingNotional:
    def test_sums_open_orders(self, mgr):
        run(mgr.submit_intent(symbol="BTC-USD", side="buy", notional=25.0))
        run(mgr.submit_intent(symbol="ETH-USD", side="buy", notional=15.0))
        assert mgr.get_pending_notional("buy") == 40.0
        assert mgr.get_pending_notional("sell") == 0.0

    def test_excludes_canceled(self, mgr):
        run(mgr.submit_intent(symbol="BTC-USD", side="buy", notional=25.0))
        oid = list(mgr._orders.keys())[0]
        run(mgr.cancel_order(oid))
        assert mgr.get_pending_notional("buy") == 0.0


class TestRecoverFromDb:
    def test_loads_open_orders(self, mgr, repo):
        repo.orders.append({
            "id": "recovered-1",
            "intent_group_id": "intent-1",
            "symbol": "BTC-USD",
            "side": "buy",
            "notional": 25,
            "qty": None,
            "limit_price": None,
            "status": "submitted",
            "replace_count": 1,
            "parent_order_id": None,
            "ttl_seconds": 60,
            "mode": "paper",
        })
        mgr.recover_from_db()
        assert len(mgr._orders) == 1
        assert mgr._orders["recovered-1"].replace_count == 1
