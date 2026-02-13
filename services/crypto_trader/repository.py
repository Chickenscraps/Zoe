from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


class CryptoRepository(Protocol):
    def insert_order(self, order: dict[str, Any]) -> None: ...
    def update_order_status(self, order_id: str, status: str, raw: dict[str, Any]) -> None: ...
    def list_open_orders(self, mode: str) -> list[dict[str, Any]]: ...
    def upsert_fill(self, fill: dict[str, Any]) -> None: ...
    def insert_holdings_snapshot(self, holdings: dict[str, Any], total_value: float, **kwargs: Any) -> None: ...
    def insert_cash_snapshot(self, cash_available: float, buying_power: float, **kwargs: Any) -> None: ...
    def insert_reconciliation_event(self, event: dict[str, Any]) -> None: ...
    def get_daily_notional(self, day: date, mode: str) -> float: ...
    def set_daily_notional(self, day: date, amount: float, mode: str) -> None: ...
    def latest_cash_snapshot(self, mode: str) -> dict[str, Any] | None: ...
    def latest_holdings_snapshot(self, mode: str) -> dict[str, Any] | None: ...
    def get_realized_pnl(self, mode: str) -> float: ...
    # Dashboard tables
    def upsert_candidate_scans(self, scans: list[dict[str, Any]]) -> None: ...
    def upsert_pnl_daily(self, row: dict[str, Any]) -> None: ...
    def upsert_health_heartbeat(self, row: dict[str, Any]) -> None: ...
    def insert_thought(self, row: dict[str, Any]) -> None: ...
    # Boot reconciliation
    def save_agent_state(self, mode: str, instance_id: str, state: dict[str, Any]) -> None: ...
    def load_agent_state(self, mode: str, instance_id: str) -> dict[str, Any] | None: ...
    def insert_boot_audit(self, record: dict[str, Any]) -> None: ...
    def update_boot_audit(self, run_id: str, updates: dict[str, Any]) -> None: ...
    # Candle data
    def upsert_candles(self, candles: list[dict[str, Any]]) -> None: ...
    # Boot context
    def recent_fills(self, mode: str, limit: int = 10) -> list[dict[str, Any]]: ...
    def recent_thoughts(self, mode: str, limit: int = 10, thought_type: str | None = None) -> list[dict[str, Any]]: ...
    def latest_candidate_scans(self, mode: str) -> list[dict[str, Any]]: ...
    def recent_orders(self, mode: str, limit: int = 10) -> list[dict[str, Any]]: ...


@dataclass
class InMemoryCryptoRepository:
    orders: list[dict[str, Any]]
    fills: list[dict[str, Any]]
    holdings_snapshots: list[dict[str, Any]]
    cash_snapshots: list[dict[str, Any]]
    reconciliation_events: list[dict[str, Any]]
    daily_notional: dict[str, float]
    _agent_states: dict[str, dict[str, Any]]
    _boot_audits: list[dict[str, Any]]

    def __init__(self) -> None:
        self.orders = []
        self.fills = []
        self.holdings_snapshots = []
        self.cash_snapshots = []
        self.reconciliation_events = []
        self.daily_notional = {}
        self._agent_states = {}
        self._boot_audits = []

    def insert_order(self, order: dict[str, Any]) -> None:
        self.orders.append(order)

    def update_order_status(self, order_id: str, status: str, raw: dict[str, Any]) -> None:
        for order in self.orders:
            if order.get("id") == order_id:
                order["status"] = status
                order["raw_response"] = raw

    def list_open_orders(self, mode: str) -> list[dict[str, Any]]:
        return [o for o in self.orders if o.get("status") in {"submitted", "partially_filled"} and o.get("mode") == mode]

    def upsert_fill(self, fill: dict[str, Any]) -> None:
        idx = next((i for i, x in enumerate(self.fills) if x.get("fill_id") == fill.get("fill_id")), None)
        if idx is None:
            self.fills.append(fill)
        else:
            self.fills[idx] = fill

    def insert_holdings_snapshot(self, holdings: dict[str, Any], total_value: float, **kwargs: Any) -> None:
        row: dict[str, Any] = {"holdings": holdings, "total_crypto_value": total_value}
        if "mode" in kwargs:
            row["mode"] = kwargs["mode"]
        self.holdings_snapshots.append(row)

    def insert_cash_snapshot(self, cash_available: float, buying_power: float, **kwargs: Any) -> None:
        row: dict[str, Any] = {"cash_available": cash_available, "buying_power": buying_power}
        if "mode" in kwargs:
            row["mode"] = kwargs["mode"]
        self.cash_snapshots.append(row)

    def insert_reconciliation_event(self, event: dict[str, Any]) -> None:
        self.reconciliation_events.append(event)

    def get_daily_notional(self, day: date, mode: str) -> float:
        return self.daily_notional.get(f"{day}:{mode}", 0.0)

    def set_daily_notional(self, day: date, amount: float, mode: str) -> None:
        self.daily_notional[f"{day}:{mode}"] = amount

    def latest_cash_snapshot(self, mode: str) -> dict[str, Any] | None:
        for snap in reversed(self.cash_snapshots):
            if snap.get("mode") == mode:
                return snap
        return self.cash_snapshots[-1] if self.cash_snapshots else None

    def latest_holdings_snapshot(self, mode: str) -> dict[str, Any] | None:
        for snap in reversed(self.holdings_snapshots):
            if snap.get("mode") == mode:
                return snap
        return self.holdings_snapshots[-1] if self.holdings_snapshots else None

    def get_realized_pnl(self, mode: str) -> float:
        pnl = 0.0
        for fill in self.fills:
            if fill.get("mode") != mode:
                continue
            side = fill.get("side")
            qty = float(fill.get("qty", 0))
            price = float(fill.get("price", 0))
            fee = float(fill.get("fee", 0))
            pnl += qty * price if side == "sell" else -qty * price
            pnl -= fee
        return pnl

    def upsert_candidate_scans(self, scans: list[dict[str, Any]]) -> None:
        pass

    def upsert_pnl_daily(self, row: dict[str, Any]) -> None:
        pass

    def upsert_health_heartbeat(self, row: dict[str, Any]) -> None:
        pass

    def insert_thought(self, row: dict[str, Any]) -> None:
        pass

    def upsert_candles(self, candles: list[dict[str, Any]]) -> None:
        pass

    def save_agent_state(self, mode: str, instance_id: str, state: dict[str, Any]) -> None:
        self._agent_states[f"{mode}:{instance_id}"] = state

    def load_agent_state(self, mode: str, instance_id: str) -> dict[str, Any] | None:
        return self._agent_states.get(f"{mode}:{instance_id}")

    def insert_boot_audit(self, record: dict[str, Any]) -> None:
        self._boot_audits.append(record)

    def update_boot_audit(self, run_id: str, updates: dict[str, Any]) -> None:
        for audit in self._boot_audits:
            if audit.get("run_id") == run_id:
                audit.update(updates)

    def recent_fills(self, mode: str, limit: int = 10) -> list[dict[str, Any]]:
        fills = [f for f in self.fills if f.get("mode") == mode]
        return fills[-limit:]

    def recent_thoughts(self, mode: str, limit: int = 10, thought_type: str | None = None) -> list[dict[str, Any]]:
        return []

    def latest_candidate_scans(self, mode: str) -> list[dict[str, Any]]:
        return []

    def recent_orders(self, mode: str, limit: int = 10) -> list[dict[str, Any]]:
        orders = [o for o in self.orders if o.get("mode") == mode]
        return orders[-limit:]
