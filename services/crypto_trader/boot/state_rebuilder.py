"""Rebuild service state from database snapshots on boot."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..repository import CryptoRepository


@dataclass
class DBState:
    open_orders: list[dict[str, Any]] = field(default_factory=list)
    holdings: dict[str, float] = field(default_factory=dict)
    cash_available: float = 0.0
    buying_power: float = 0.0
    daily_notional_used: float = 0.0


def rebuild_state_from_db(repo: CryptoRepository, mode: str) -> DBState:
    """Load the latest known state from Supabase snapshots."""
    open_orders = repo.list_open_orders(mode)

    holdings_snap = repo.latest_holdings_snapshot(mode) or {}
    holdings = holdings_snap.get("holdings", {})
    if isinstance(holdings, dict):
        holdings = {k: float(v) for k, v in holdings.items()}
    else:
        holdings = {}

    cash_snap = repo.latest_cash_snapshot(mode) or {}
    cash_available = float(cash_snap.get("cash_available", 0.0))
    buying_power = float(cash_snap.get("buying_power", 0.0))

    daily_notional = repo.get_daily_notional(date.today(), mode)

    return DBState(
        open_orders=open_orders,
        holdings=holdings,
        cash_available=cash_available,
        buying_power=buying_power,
        daily_notional_used=daily_notional,
    )
