"""Startup hydration sequence — loads system state before trading begins.

Hydration order:
1. Load market catalog from Supabase (refresh from Kraken if stale)
2. Fetch current balances + open orders + recent fills from exchange
3. Reconcile DB state vs exchange state
4. Write initial health heartbeat
5. Mark system READY
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class HydrationResult:
    """Result of startup hydration."""

    def __init__(self) -> None:
        self.cash_balance: float = 0.0
        self.holdings: dict[str, float] = {}
        self.open_orders: list[dict] = []
        self.catalog_pairs: int = 0
        self.reconciliation_status: str = "pending"
        self.errors: list[str] = []
        self.ready: bool = False

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class StartupHydrator:
    """Executes startup hydration sequence."""

    def __init__(
        self,
        supabase_client: Any,
        exchange_client: Any,
        mode: str = "paper",
    ):
        self._sb = supabase_client
        self._exchange = exchange_client
        self._mode = mode

    async def hydrate(self) -> HydrationResult:
        """Run full startup hydration sequence."""
        result = HydrationResult()
        logger.info("Starting hydration sequence (mode=%s)", self._mode)

        # 1. Check market catalog freshness
        try:
            resp = self._sb.table("market_catalog").select(
                "symbol", count="exact"
            ).execute()
            result.catalog_pairs = resp.count or 0
            if result.catalog_pairs == 0:
                logger.warning("Market catalog empty — market_data_ws service may not be running")
            else:
                logger.info("Market catalog: %d pairs", result.catalog_pairs)
        except Exception as e:
            result.errors.append(f"Catalog check failed: {e}")
            logger.warning("Catalog check failed: %s", e)

        # 2. Fetch exchange state
        try:
            balances = await self._exchange.get_account_balances()
            if isinstance(balances, dict):
                for key in ("ZUSD", "USD", "USDT"):
                    if key in balances:
                        result.cash_balance = float(balances[key])
                        break
                if result.cash_balance == 0:
                    bp = balances.get("crypto_buying_power", balances.get("buying_power"))
                    if bp is not None:
                        result.cash_balance = float(bp)
            logger.info("Cash balance: $%.2f", result.cash_balance)
        except Exception as e:
            result.errors.append(f"Balance fetch failed: {e}")
            logger.warning("Balance fetch failed: %s", e)

        try:
            holdings = await self._exchange.get_holdings()
            if isinstance(holdings, dict):
                result.holdings = {k: float(v) for k, v in holdings.items() if float(v) > 1e-8}
            logger.info("Holdings: %d positions", len(result.holdings))
        except Exception as e:
            result.errors.append(f"Holdings fetch failed: {e}")
            logger.warning("Holdings fetch failed: %s", e)

        # 3. Fetch open orders
        try:
            resp = self._sb.table("order_intents").select("*").eq(
                "mode", self._mode
            ).in_("status", ["submitted", "acked", "partial_fill"]).execute()
            result.open_orders = resp.data or []
            logger.info("Open order intents: %d", len(result.open_orders))
        except Exception as e:
            # Table may not exist yet
            logger.debug("Order intents fetch failed (may not exist): %s", e)

        # 4. Run reconciliation
        try:
            from services.reconciliation.broker_vs_db import BrokerReconciler
            reconciler = BrokerReconciler(self._sb, self._exchange)
            recon_result = await reconciler.reconcile(self._mode)
            result.reconciliation_status = recon_result.status
            if recon_result.status != "ok":
                logger.warning("Hydration reconciliation: %s", recon_result.details)
        except Exception as e:
            result.reconciliation_status = "error"
            result.errors.append(f"Reconciliation failed: {e}")
            logger.warning("Reconciliation failed: %s", e)

        # 5. Write heartbeat
        try:
            self._sb.table("health_heartbeat").upsert({
                "component": "hydration",
                "status": "ok" if not result.has_errors else "degraded",
                "message": f"Hydrated: cash=${result.cash_balance:.2f}, {len(result.holdings)} positions, recon={result.reconciliation_status}",
                "mode": self._mode,
            }, on_conflict="component,mode").execute()
        except Exception as e:
            logger.warning("Heartbeat write failed: %s", e)

        result.ready = not result.has_errors or result.reconciliation_status != "error"
        logger.info(
            "Hydration complete: ready=%s, cash=$%.2f, %d positions, recon=%s",
            result.ready, result.cash_balance, len(result.holdings), result.reconciliation_status,
        )

        return result
