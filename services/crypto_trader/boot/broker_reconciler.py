"""Fetch broker state and compute diffs against DB state."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import CryptoTraderConfig
from .state_rebuilder import DBState


@dataclass
class BrokerState:
    cash_available: float = 0.0
    buying_power: float = 0.0
    holdings: dict[str, float] = field(default_factory=dict)


@dataclass
class StateDiffs:
    cash_diff: float = 0.0
    holdings_diffs: dict[str, float] = field(default_factory=dict)
    missing_orders: list[str] = field(default_factory=list)


async def fetch_broker_state(client: Any, config: CryptoTraderConfig) -> BrokerState:
    """Fetch current broker state. In paper mode, returns empty (DB is source of truth)."""
    if config.mode == "paper":
        return BrokerState()

    balances = await client.get_account_balances()
    holdings_resp = await client.get_holdings()

    # Handle both RH format (cash_available) and Kraken format (ZUSD)
    cash = float(
        balances.get("cash_available")
        or balances.get("cash")
        or balances.get("ZUSD")
        or balances.get("USD")
        or 0.0
    )
    bp = float(balances.get("buying_power") or cash)
    holdings = {
        item["symbol"]: float(item.get("quantity", 0.0))
        for item in holdings_resp.get("results", holdings_resp if isinstance(holdings_resp, list) else [])
    }

    return BrokerState(cash_available=cash, buying_power=bp, holdings=holdings)


def compute_diffs(db_state: DBState, broker_state: BrokerState, mode: str) -> StateDiffs:
    """Compare DB state against broker state and return diffs."""
    if mode == "paper":
        # Paper mode: DB is truth, no broker diffs
        return StateDiffs()

    cash_diff = db_state.cash_available - broker_state.cash_available

    all_symbols = set(db_state.holdings) | set(broker_state.holdings)
    holdings_diffs = {}
    for sym in sorted(all_symbols):
        db_qty = db_state.holdings.get(sym, 0.0)
        broker_qty = broker_state.holdings.get(sym, 0.0)
        diff = db_qty - broker_qty
        if abs(diff) > 0.0000001:
            holdings_diffs[sym] = diff

    # Check for open orders in DB that may no longer exist at broker
    missing_orders: list[str] = []
    # (Order verification would require individual API calls; skip for now)

    return StateDiffs(
        cash_diff=cash_diff,
        holdings_diffs=holdings_diffs,
        missing_orders=missing_orders,
    )
