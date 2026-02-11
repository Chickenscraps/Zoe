from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


class CryptoRepository(Protocol):
    def insert_order(self, order: dict[str, Any]) -> None: ...
    def update_order_status(self, order_id: str, status: str, raw: dict[str, Any]) -> None: ...
    def list_open_orders(self) -> list[dict[str, Any]]: ...
    def upsert_fill(self, fill: dict[str, Any]) -> None: ...
    def insert_holdings_snapshot(self, holdings: dict[str, Any], total_value: float) -> None: ...
    def insert_cash_snapshot(self, cash_available: float, buying_power: float) -> None: ...
    def insert_reconciliation_event(self, event: dict[str, Any]) -> None: ...
    def get_daily_notional(self, day: date) -> float: ...
    def set_daily_notional(self, day: date, amount: float) -> None: ...
    def latest_cash_snapshot(self) -> dict[str, Any] | None: ...
    def latest_holdings_snapshot(self) -> dict[str, Any] | None: ...
    def get_realized_pnl(self) -> float: ...


@dataclass
class InMemoryCryptoRepository:
    orders: list[dict[str, Any]]
    fills: list[dict[str, Any]]
    holdings_snapshots: list[dict[str, Any]]
    cash_snapshots: list[dict[str, Any]]
    reconciliation_events: list[dict[str, Any]]
    daily_notional: dict[str, float]

    def __init__(self) -> None:
        self.orders = []
        self.fills = []
        self.holdings_snapshots = []
        self.cash_snapshots = []
        self.reconciliation_events = []
        self.daily_notional = {}

    def insert_order(self, order: dict[str, Any]) -> None:
        self.orders.append(order)

    def update_order_status(self, order_id: str, status: str, raw: dict[str, Any]) -> None:
        for order in self.orders:
            if order.get("id") == order_id:
                order["status"] = status
                order["raw_response"] = raw

    def list_open_orders(self) -> list[dict[str, Any]]:
        return [o for o in self.orders if o.get("status") in {"submitted", "partially_filled"}]

    def upsert_fill(self, fill: dict[str, Any]) -> None:
        idx = next((i for i, x in enumerate(self.fills) if x.get("fill_id") == fill.get("fill_id")), None)
        if idx is None:
            self.fills.append(fill)
        else:
            self.fills[idx] = fill

    def insert_holdings_snapshot(self, holdings: dict[str, Any], total_value: float) -> None:
        self.holdings_snapshots.append({"holdings": holdings, "total_crypto_value": total_value})

    def insert_cash_snapshot(self, cash_available: float, buying_power: float) -> None:
        self.cash_snapshots.append({"cash_available": cash_available, "buying_power": buying_power})

    def insert_reconciliation_event(self, event: dict[str, Any]) -> None:
        self.reconciliation_events.append(event)

    def get_daily_notional(self, day: date) -> float:
        return self.daily_notional.get(str(day), 0.0)

    def set_daily_notional(self, day: date, amount: float) -> None:
        self.daily_notional[str(day)] = amount

    def latest_cash_snapshot(self) -> dict[str, Any] | None:
        return self.cash_snapshots[-1] if self.cash_snapshots else None

    def latest_holdings_snapshot(self) -> dict[str, Any] | None:
        return self.holdings_snapshots[-1] if self.holdings_snapshots else None

    def get_realized_pnl(self) -> float:
        pnl = 0.0
        for fill in self.fills:
            side = fill.get("side")
            qty = float(fill.get("qty", 0))
            price = float(fill.get("price", 0))
            fee = float(fill.get("fee", 0))
            pnl += qty * price if side == "sell" else -qty * price
            pnl -= fee
        return pnl
