from __future__ import annotations

from dataclasses import dataclass

from services.crypto_trader.config import CONFIRM_PHRASE, CryptoTraderConfig
from services.crypto_trader.repository import InMemoryCryptoRepository
from services.crypto_trader.trader import CryptoTraderService


@dataclass
class StubClient:
    order_status: str = "submitted"

    def get_account_balances(self):
        return {"cash_available": 100.0, "buying_power": 100.0}

    def get_holdings(self):
        return {"results": [{"symbol": "BTC-USD", "quantity": "0.0", "market_value": "0"}]}

    def place_order(self, **kwargs):
        return {"id": "ord-1", "status": self.order_status, "echo": kwargs}

    def get_order(self, order_id: str):
        return {"id": order_id, "status": self.order_status}

    def get_order_fills(self, order_id: str):
        return {"results": []}


def make_service() -> CryptoTraderService:
    cfg = CryptoTraderConfig(
        admin_user_id="admin",
        rh_live_trading=True,
        rh_live_confirm=CONFIRM_PHRASE,
        max_notional_per_trade=10,
        max_daily_notional=50,
        max_open_positions=3,
    )
    return CryptoTraderService(StubClient(), InMemoryCryptoRepository(), cfg)


def test_non_admin_cannot_trade() -> None:
    svc = make_service()
    try:
        svc.place_order(initiator_id="nope", symbol="BTC-USD", side="buy", notional=1)
        raise AssertionError("Expected permission error")
    except PermissionError:
        pass


def test_symbol_guard_blocks_non_crypto() -> None:
    svc = make_service()
    try:
        svc.place_order(initiator_id="admin", symbol="AAPL", side="buy", notional=1)
        raise AssertionError("Expected symbol guard error")
    except ValueError as err:
        assert "crypto" in str(err).lower()


def test_daily_notional_limit_enforced() -> None:
    svc = make_service()
    svc.place_order(initiator_id="admin", symbol="BTC-USD", side="buy", notional=10)
    svc.place_order(initiator_id="admin", symbol="BTC-USD", side="buy", notional=10)
    svc.place_order(initiator_id="admin", symbol="BTC-USD", side="buy", notional=10)
    svc.place_order(initiator_id="admin", symbol="BTC-USD", side="buy", notional=10)
    svc.place_order(initiator_id="admin", symbol="BTC-USD", side="buy", notional=10)
    try:
        svc.place_order(initiator_id="admin", symbol="BTC-USD", side="buy", notional=1)
        raise AssertionError("Expected daily notional block")
    except ValueError as err:
        assert "MAX_DAILY_NOTIONAL" in str(err)
