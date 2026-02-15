"""Broker vs DB reconciliation — compare exchange state with Supabase.

Detects:
- Cash mismatch (exchange balance vs DB snapshot)
- Position mismatch (exchange holdings vs DB positions)
- Orphaned positions (in DB but not on exchange)
- Missing fills (on exchange but not in DB)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Tolerance thresholds
CASH_TOLERANCE = 0.01  # $0.01 rounding tolerance
QTY_TOLERANCE = 1e-8   # Minimum qty difference to report


@dataclass
class ReconciliationResult:
    """Result of a reconciliation check."""
    status: str  # "ok" | "degraded" | "mismatch"
    cash_exchange: float
    cash_db: float
    cash_diff: float
    holdings_exchange: dict[str, float]
    holdings_db: dict[str, float]
    holdings_diffs: dict[str, float]
    orphaned_positions: list[str]
    missing_on_exchange: list[str]
    timestamp: datetime
    details: str = ""


class BrokerReconciler:
    """Compares exchange state with DB state and reports mismatches."""

    def __init__(
        self,
        supabase_client: Any,
        exchange_client: Any,
    ):
        self._sb = supabase_client
        self._exchange = exchange_client

    async def reconcile(self, mode: str = "paper") -> ReconciliationResult:
        """Run full reconciliation check."""
        now = datetime.now(timezone.utc)

        # 1. Get exchange state
        exchange_cash = await self._get_exchange_cash()
        exchange_holdings = await self._get_exchange_holdings()

        # 2. Get DB state
        db_cash = await self._get_db_cash(mode)
        db_holdings = await self._get_db_holdings(mode)

        # 3. Compare cash
        cash_diff = abs(exchange_cash - db_cash)

        # 4. Compare holdings
        all_symbols = set(list(exchange_holdings.keys()) + list(db_holdings.keys()))
        holdings_diffs: dict[str, float] = {}
        orphaned: list[str] = []
        missing: list[str] = []

        for sym in all_symbols:
            ex_qty = exchange_holdings.get(sym, 0.0)
            db_qty = db_holdings.get(sym, 0.0)
            diff = ex_qty - db_qty

            if abs(diff) > QTY_TOLERANCE:
                holdings_diffs[sym] = diff

            if ex_qty < QTY_TOLERANCE and db_qty > QTY_TOLERANCE:
                orphaned.append(sym)
            elif db_qty < QTY_TOLERANCE and ex_qty > QTY_TOLERANCE:
                missing.append(sym)

        # 5. Determine status
        status = "ok"
        details_parts: list[str] = []

        if cash_diff > CASH_TOLERANCE:
            status = "degraded"
            details_parts.append(f"Cash diff: ${cash_diff:.2f}")

        if holdings_diffs:
            status = "degraded"
            for sym, diff in holdings_diffs.items():
                details_parts.append(f"{sym}: qty diff {diff:.8f}")

        if orphaned:
            status = "mismatch"
            details_parts.append(f"Orphaned in DB: {', '.join(orphaned)}")

        if missing:
            status = "degraded"
            details_parts.append(f"Missing in DB: {', '.join(missing)}")

        result = ReconciliationResult(
            status=status,
            cash_exchange=exchange_cash,
            cash_db=db_cash,
            cash_diff=cash_diff,
            holdings_exchange=exchange_holdings,
            holdings_db=db_holdings,
            holdings_diffs=holdings_diffs,
            orphaned_positions=orphaned,
            missing_on_exchange=missing,
            timestamp=now,
            details="; ".join(details_parts) if details_parts else "All reconciled",
        )

        # 6. Write event to DB
        await self._write_event(result, mode)

        if status != "ok":
            logger.warning("Reconciliation %s: %s", status, result.details)
        else:
            logger.debug("Reconciliation OK")

        return result

    async def _get_exchange_cash(self) -> float:
        """Get USD cash from exchange."""
        try:
            data = await self._exchange.get_account_balances()
            if isinstance(data, dict):
                for key in ("ZUSD", "USD", "USDT"):
                    if key in data:
                        return float(data[key])
                # RH compat
                bp = data.get("crypto_buying_power", data.get("buying_power"))
                if bp is not None:
                    return float(bp)
        except Exception as e:
            logger.warning("Exchange cash fetch failed: %s", e)
        return 0.0

    async def _get_exchange_holdings(self) -> dict[str, float]:
        """Get holdings from exchange."""
        try:
            data = await self._exchange.get_holdings()
            if isinstance(data, dict):
                # get_holdings() returns {"results": [{"symbol": "BTC-USD", "quantity_float": 0.5, ...}]}
                results = data.get("results", [])
                if isinstance(results, list):
                    return {
                        item["symbol"]: float(item.get("quantity_float", item.get("quantity", 0)))
                        for item in results
                        if float(item.get("quantity_float", item.get("quantity", 0))) > QTY_TOLERANCE
                    }
                # Fallback: flat dict
                return {k: float(v) for k, v in data.items() if float(v) > QTY_TOLERANCE}
        except Exception as e:
            logger.warning("Exchange holdings fetch failed: %s", e)
        return {}

    async def _get_db_cash(self, mode: str) -> float:
        """Get latest cash from DB snapshots."""
        try:
            resp = self._sb.table("crypto_cash_snapshots").select(
                "buying_power"
            ).eq("mode", mode).order("taken_at", desc=True).limit(1).execute()
            rows = resp.data or []
            if rows:
                return float(rows[0].get("buying_power", 0))
        except Exception as e:
            logger.warning("DB cash fetch failed: %s", e)
        return 0.0

    async def _get_db_holdings(self, mode: str) -> dict[str, float]:
        """Get latest holdings from DB snapshots."""
        try:
            resp = self._sb.table("crypto_holdings_snapshots").select(
                "holdings"
            ).eq("mode", mode).order("taken_at", desc=True).limit(1).execute()
            rows = resp.data or []
            if rows and rows[0].get("holdings"):
                holdings = rows[0]["holdings"]
                if isinstance(holdings, dict):
                    return {k: float(v) for k, v in holdings.items() if float(v) > QTY_TOLERANCE}
        except Exception as e:
            logger.warning("DB holdings fetch failed: %s", e)
        return {}

    async def _write_event(self, result: ReconciliationResult, mode: str) -> None:
        """Write reconciliation event to DB."""
        try:
            self._sb.table("crypto_reconciliation_events").insert({
                "local_cash": result.cash_db,
                "rh_cash": result.cash_exchange,
                "cash_diff": result.cash_diff,
                "local_holdings": result.holdings_db,
                "rh_holdings": result.holdings_exchange,
                "holdings_diff": result.holdings_diffs,
                "status": "ok" if result.status == "ok" else "degraded",
                "reason": result.details,
                "mode": mode,
            }).execute()
        except Exception as e:
            logger.warning("Reconciliation event write failed: %s", e)
