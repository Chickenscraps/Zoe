"""Cash event ledger — deposits, withdrawals, and transfers.

Records non-trading cash movements so they don't pollute P&L calculations.
Deposits/withdrawals are NOT P&L — they change cash balance but not performance.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CashEventLedger:
    """Records deposits, withdrawals, and other cash events to Supabase."""

    def __init__(self, supabase_client: Any):
        self._sb = supabase_client

    async def record_event(
        self,
        event_type: str,  # "deposit" | "withdrawal" | "transfer_in" | "transfer_out"
        amount: float,
        currency: str = "USD",
        description: str = "",
        external_ref: str = "",
        mode: str = "paper",
    ) -> None:
        """Record a cash event."""
        try:
            self._sb.table("cash_events").insert({
                "event_type": event_type,
                "amount": amount,
                "currency": currency,
                "description": description,
                "external_ref": external_ref,
                "mode": mode,
            }).execute()
            logger.info("Cash event recorded: %s %.2f %s", event_type, amount, currency)
        except Exception as e:
            logger.warning("Cash event write failed: %s", e)

    async def get_total_deposits(self, mode: str = "paper") -> float:
        """Sum of all deposits."""
        try:
            resp = self._sb.table("cash_events").select(
                "amount"
            ).eq("mode", mode).in_(
                "event_type", ["deposit", "transfer_in"]
            ).execute()
            return sum(float(r.get("amount", 0)) for r in (resp.data or []))
        except Exception as e:
            logger.warning("Deposit total read failed: %s", e)
            return 0.0

    async def get_total_withdrawals(self, mode: str = "paper") -> float:
        """Sum of all withdrawals."""
        try:
            resp = self._sb.table("cash_events").select(
                "amount"
            ).eq("mode", mode).in_(
                "event_type", ["withdrawal", "transfer_out"]
            ).execute()
            return sum(float(r.get("amount", 0)) for r in (resp.data or []))
        except Exception as e:
            logger.warning("Withdrawal total read failed: %s", e)
            return 0.0

    async def get_net_deposits(self, mode: str = "paper") -> float:
        """Net deposits (deposits - withdrawals). This is the invested capital."""
        deposits = await self.get_total_deposits(mode)
        withdrawals = await self.get_total_withdrawals(mode)
        return deposits - withdrawals

    async def get_events(
        self, mode: str = "paper", limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get recent cash events."""
        try:
            resp = self._sb.table("cash_events").select("*").eq(
                "mode", mode
            ).order("created_at", desc=True).limit(limit).execute()
            return resp.data or []
        except Exception as e:
            logger.warning("Cash events read failed: %s", e)
            return []
