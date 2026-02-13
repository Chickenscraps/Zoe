"""Fee tracker — extract and persist per-fill fees to fee_ledger.

Kraken reports exact fee per fill in trade response.
This module extracts fees from fill data and writes to the fee_ledger table.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FeeTracker:
    """Tracks and persists trading fees to Supabase fee_ledger."""

    def __init__(self, supabase_client: Any):
        self._sb = supabase_client

    async def record_fee(
        self,
        fill_id: str,
        order_id: str,
        symbol: str,
        fee_amount: float,
        fee_currency: str = "USD",
        fee_type: str = "trading",
        mode: str = "paper",
    ) -> None:
        """Record a single fee entry in the ledger."""
        if fee_amount <= 0:
            return

        try:
            self._sb.table("fee_ledger").upsert({
                "fill_id": fill_id,
                "order_id": order_id,
                "symbol": symbol,
                "fee_amount": fee_amount,
                "fee_currency": fee_currency,
                "fee_type": fee_type,
                "mode": mode,
            }, on_conflict="fill_id").execute()
        except Exception as e:
            logger.warning("Fee ledger write failed: %s", e)

    async def get_total_fees(self, mode: str = "paper") -> float:
        """Get total fees paid across all trades."""
        try:
            resp = self._sb.table("fee_ledger").select(
                "fee_amount"
            ).eq("mode", mode).execute()
            return sum(float(row.get("fee_amount", 0)) for row in (resp.data or []))
        except Exception as e:
            logger.warning("Fee ledger read failed: %s", e)
            return 0.0

    async def get_fees_by_symbol(self, mode: str = "paper") -> dict[str, float]:
        """Get fees grouped by symbol."""
        try:
            resp = self._sb.table("fee_ledger").select(
                "symbol, fee_amount"
            ).eq("mode", mode).execute()
            fees: dict[str, float] = {}
            for row in (resp.data or []):
                sym = row["symbol"]
                fees[sym] = fees.get(sym, 0) + float(row.get("fee_amount", 0))
            return fees
        except Exception as e:
            logger.warning("Fee ledger read failed: %s", e)
            return {}

    async def get_today_fees(self, mode: str = "paper") -> float:
        """Get fees paid today."""
        from datetime import date
        today = str(date.today())
        try:
            resp = self._sb.table("fee_ledger").select(
                "fee_amount"
            ).eq("mode", mode).gte("created_at", today).execute()
            return sum(float(row.get("fee_amount", 0)) for row in (resp.data or []))
        except Exception as e:
            logger.warning("Today fee read failed: %s", e)
            return 0.0
