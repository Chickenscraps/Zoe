from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any, List, Optional
from supabase import Client

# We wrap blocking calls in asyncio.to_thread to keep the main loop responsive.

class SupabaseCryptoRepository:
    def __init__(self, supabase_client: Client):
        self.db = supabase_client

    async def _run(self, func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    async def insert_order(self, order: dict[str, Any]) -> None:
        def _op():
            try:
                self.db.table("crypto_orders").insert(order).execute()
            except Exception as e:
                print(f"❌ Failed to insert order {order.get('id')}: {e}")
        await self._run(_op)

    async def update_order_status(self, order_id: str, status: str, raw: dict[str, Any]) -> None:
        def _op():
            try:
                self.db.table("crypto_orders").update(
                    {"status": status, "raw_response": raw, "updated_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", order_id).execute()
            except Exception as e:
                print(f"❌ Failed to update order {order_id}: {e}")
        await self._run(_op)

    async def list_open_orders(self) -> List[dict[str, Any]]:
        def _op():
            try:
                res = self.db.table("crypto_orders").select("*").in_("status", ["submitted", "partially_filled", "pending"]).execute()
                return res.data if res.data else []
            except Exception as e:
                print(f"❌ Failed to list open orders: {e}")
                return []
        return await self._run(_op)

    async def upsert_fill(self, fill: dict[str, Any]) -> None:
        def _op():
            try:
                self.db.table("crypto_fills").upsert(fill).execute()
            except Exception as e:
                print(f"❌ Failed to upsert fill {fill.get('fill_id')}: {e}")
        await self._run(_op)

    async def record_audit_event(self, component: str, event: str, level: str = "info", details: dict = None):
        def _op():
            try:
                self.db.table("crypto_audit_log").insert({
                    "component": component,
                    "event": event,
                    "level": level,
                    "details": details or {},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }).execute()
            except Exception as e:
                print(f"❌ Failed to record audit log: {e}")
        await self._run(_op)

    # --- Snapshots (Legacy support + New Schema) ---
    async def insert_cash_snapshot(self, cash_available: float, buying_power: float) -> None:
        def _op():
            try:
                self.db.table("crypto_cash_snapshots").insert({
                    "taken_at": datetime.now(timezone.utc).isoformat(),
                    "cash_available": cash_available,
                    "buying_power": buying_power,
                }).execute()
            except Exception as e:
                print(f"❌ Failed to insert cash snapshot: {e}")
        await self._run(_op)

    async def insert_holdings_snapshot(self, holdings: dict[str, Any], total_value: float) -> None:
        def _op():
            try:
                self.db.table("crypto_holdings_snapshots").insert({
                    "taken_at": datetime.now(timezone.utc).isoformat(),
                    "holdings": holdings,
                    "total_crypto_value": total_value,
                }).execute()
            except Exception as e:
                print(f"❌ Failed to insert holdings snapshot: {e}")
        await self._run(_op)

    async def get_daily_notional(self, day: date) -> float:
        def _op():
            try:
                res = self.db.table("daily_notional").select("amount").eq("day", str(day)).maybe_single().execute()
                return float(res.data["amount"]) if res.data else 0.0
            except Exception as e:
                print(f"❌ Failed to get daily notional: {e}")
                return 0.0
        return await self._run(_op)

    async def set_daily_notional(self, day: date, amount: float) -> None:
        def _op():
            try:
                self.db.table("daily_notional").upsert(
                    {"day": str(day), "amount": amount}, on_conflict="day"
                ).execute()
            except Exception as e:
                print(f"❌ Failed to set daily notional: {e}")
        await self._run(_op)

    async def get_positions_count(self) -> int:
        # Count non-zero positions from latest snapshot or a positions table
        # For now using snapshot for backward compat
        def _op():
            try:
                res = self.db.table("crypto_holdings_snapshots").select("holdings").order("taken_at", desc=True).limit(1).maybe_single().execute()
                if not res.data: return 0
                holdings = res.data.get("holdings", {})
                return len([k for k, v in holdings.items() if float(v) > 0])
            except Exception as e:
                print(f"❌ Failed to get positions count: {e}")
                return 0
        return await self._run(_op)

    async def get_daily_realized_pnl(self, day: date) -> float:
        # TODO: Implement accurate daily PnL query
        return 0.0

    async def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        # Return DB candles
        def _op():
            try:
                res = self.db.table("crypto_candles").select("*").eq("symbol", symbol).eq("timeframe", timeframe).order("bucket", desc=True).limit(limit).execute()
                # Sort ascending
                data = res.data or []
                data.reverse()
                return data 
            except Exception as e:
                print(f"❌ Failed to fetch candles: {e}")
                return []
        # Convert to Candle objects in MarketData provider, here just return dicts
        return await self._run(_op)

    async def latest_cash_snapshot(self) -> dict[str, Any] | None:
        def _op():
            try:
                res = self.db.table("crypto_cash_snapshots").select("*").order("taken_at", desc=True).limit(1).maybe_single().execute()
                return res.data
            except Exception as e:
                print(f"❌ Failed to get latest cash snapshot: {e}")
                return None
        return await self._run(_op)
    
    async def insert_reconciliation_event(self, event: dict[str, Any]) -> None:
        def _op():
            try:
                self.db.table("crypto_reconciliation_events").insert(event).execute()
            except Exception as e:
                print(f"❌ Failed to insert reconciliation event: {e}")
        await self._run(_op)

    async def upsert_ticker(self, symbol: str, price: float) -> None:
        def _op():
            try:
                self.db.table("crypto_tickers").upsert({
                    "symbol": symbol,
                    "price": price,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }).execute()
            except Exception as e:
                print(f"❌ Failed to upsert ticker {symbol}: {e}")
        await self._run(_op)
