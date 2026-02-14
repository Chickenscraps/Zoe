from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Any

from supabase import create_client, Client


class SupabaseCryptoRepository:
    """Persists crypto trader data to Supabase with mode isolation."""

    def __init__(self, client: Client | None = None):
        if client is not None:
            self.sb = client
        else:
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_SERVICE_KEY", "")
            if not url or not key:
                raise RuntimeError(
                    "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY env vars"
                )
            self.sb = create_client(url, key)

    # ── Orders ──

    def insert_order(self, order: dict[str, Any]) -> None:
        self.sb.table("crypto_orders").insert(order).execute()

    def update_order_status(self, order_id: str, status: str, raw: dict[str, Any]) -> None:
        self.sb.table("crypto_orders").update(
            {"status": status, "raw_response": raw}
        ).eq("id", order_id).execute()

    def list_open_orders(self, mode: str) -> list[dict[str, Any]]:
        resp = (
            self.sb.table("crypto_orders")
            .select("*")
            .eq("mode", mode)
            .in_("status", ["submitted", "partially_filled"])
            .execute()
        )
        return resp.data or []

    # ── Fills ──

    def upsert_fill(self, fill: dict[str, Any]) -> None:
        self.sb.table("crypto_fills").upsert(fill, on_conflict="fill_id").execute()

    # ── Snapshots ──

    def insert_holdings_snapshot(self, holdings: dict[str, Any], total_value: float, **kwargs: Any) -> None:
        row: dict[str, Any] = {"holdings": holdings, "total_crypto_value": total_value}
        if "mode" in kwargs:
            row["mode"] = kwargs["mode"]
        self.sb.table("crypto_holdings_snapshots").insert(row).execute()

    def insert_cash_snapshot(self, cash_available: float, buying_power: float, **kwargs: Any) -> None:
        row: dict[str, Any] = {"cash_available": cash_available, "buying_power": buying_power}
        if "mode" in kwargs:
            row["mode"] = kwargs["mode"]
        self.sb.table("crypto_cash_snapshots").insert(row).execute()

    def insert_reconciliation_event(self, event: dict[str, Any]) -> None:
        self.sb.table("crypto_reconciliation_events").insert(event).execute()

    # ── Daily notional ──

    def get_daily_notional(self, day: date, mode: str) -> float:
        resp = (
            self.sb.table("daily_notional")
            .select("amount")
            .eq("day", str(day))
            .eq("mode", mode)
            .maybe_single()
            .execute()
        )
        if resp and resp.data:
            return float(resp.data.get("amount", 0))
        return 0.0

    def set_daily_notional(self, day: date, amount: float, mode: str) -> None:
        self.sb.table("daily_notional").upsert(
            {"day": str(day), "amount": amount, "mode": mode},
            on_conflict="day,mode",
        ).execute()

    # ── Latest snapshots (mode-filtered) ──

    def latest_cash_snapshot(self, mode: str) -> dict[str, Any] | None:
        resp = (
            self.sb.table("crypto_cash_snapshots")
            .select("*")
            .eq("mode", mode)
            .order("taken_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return resp.data if resp else None

    def latest_holdings_snapshot(self, mode: str) -> dict[str, Any] | None:
        resp = (
            self.sb.table("crypto_holdings_snapshots")
            .select("*")
            .eq("mode", mode)
            .order("taken_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return resp.data if resp else None

    # ── Dashboard tables ──

    def upsert_candidate_scans(self, scans: list[dict[str, Any]]) -> None:
        if not scans:
            return
        self.sb.table("candidate_scans").insert(scans).execute()

    def upsert_pnl_daily(self, row: dict[str, Any]) -> None:
        self.sb.table("pnl_daily").upsert(
            row, on_conflict="date,instance_id,mode"
        ).execute()

    def upsert_health_heartbeat(self, row: dict[str, Any]) -> None:
        self.sb.table("health_heartbeat").upsert(
            row, on_conflict="instance_id,component,mode"
        ).execute()

    def insert_thought(self, row: dict[str, Any]) -> None:
        self.sb.table("thoughts").insert(row).execute()

    def upsert_candles(self, candles: list[dict[str, Any]]) -> None:
        """Persist finalized candles to Supabase crypto_candles table."""
        if not candles:
            return
        try:
            self.sb.table("crypto_candles").upsert(
                candles, on_conflict="symbol,timeframe,open_time,mode"
            ).execute()
        except Exception as e:
            print(f"[REPO] candle upsert error: {e}")

    def get_realized_pnl(self, mode: str) -> float:
        resp = (
            self.sb.table("crypto_fills")
            .select("side, qty, price, fee")
            .eq("mode", mode)
            .execute()
        )
        pnl = 0.0
        for fill in resp.data or []:
            qty = float(fill.get("qty", 0))
            price = float(fill.get("price", 0))
            fee = float(fill.get("fee", 0))
            gross = qty * price
            pnl += (gross if fill.get("side") == "sell" else -gross) - fee
        return pnl

    # ── Boot reconciliation ──

    def save_agent_state(self, mode: str, instance_id: str, state: dict[str, Any]) -> None:
        self.sb.table("agent_state").upsert(
            {
                "mode": mode,
                "instance_id": instance_id,
                "state": state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="mode,instance_id",
        ).execute()

    def load_agent_state(self, mode: str, instance_id: str) -> dict[str, Any] | None:
        resp = (
            self.sb.table("agent_state")
            .select("state")
            .eq("mode", mode)
            .eq("instance_id", instance_id)
            .maybe_single()
            .execute()
        )
        if resp and resp.data:
            return resp.data.get("state")
        return None

    def insert_boot_audit(self, record: dict[str, Any]) -> None:
        self.sb.table("boot_audit").insert(record).execute()

    def update_boot_audit(self, run_id: str, updates: dict[str, Any]) -> None:
        self.sb.table("boot_audit").update(updates).eq("run_id", run_id).execute()

    # ── Boot context (recent history) ──

    def recent_fills(self, mode: str, limit: int = 10) -> list[dict[str, Any]]:
        try:
            resp = (
                self.sb.table("crypto_fills")
                .select("*")
                .eq("mode", mode)
                .order("executed_at", desc=True)
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception:
            return []

    def recent_thoughts(self, mode: str, limit: int = 10, thought_type: str | None = None) -> list[dict[str, Any]]:
        try:
            query = (
                self.sb.table("thoughts")
                .select("*")
                .eq("mode", mode)
            )
            if thought_type:
                query = query.eq("type", thought_type)
            resp = query.order("created_at", desc=True).limit(limit).execute()
            return resp.data or []
        except Exception:
            return []

    def latest_candidate_scans(self, mode: str) -> list[dict[str, Any]]:
        """Fetch the most recent batch of candidate scans."""
        try:
            # Step 1: get the latest timestamp
            latest_resp = (
                self.sb.table("candidate_scans")
                .select("created_at")
                .eq("mode", mode)
                .order("created_at", desc=True)
                .limit(1)
                .maybe_single()
                .execute()
            )
            if not latest_resp or not latest_resp.data:
                return []
            latest_ts = latest_resp.data["created_at"]

            # Step 2: fetch all scans from that batch
            resp = (
                self.sb.table("candidate_scans")
                .select("*")
                .eq("mode", mode)
                .eq("created_at", latest_ts)
                .order("score", desc=True)
                .execute()
            )
            return resp.data or []
        except Exception:
            return []

    def recent_orders(self, mode: str, limit: int = 10) -> list[dict[str, Any]]:
        try:
            resp = (
                self.sb.table("crypto_orders")
                .select("*")
                .eq("mode", mode)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception:
            return []

    # ── Market data (Kraken) ──

    def upsert_market_catalog(self, rows: list[dict[str, Any]]) -> None:
        """Upsert pairs into market_catalog from AssetPairs response."""
        if not rows:
            return
        try:
            self.sb.table("market_catalog").upsert(
                rows, on_conflict="symbol"
            ).execute()
        except Exception as e:
            print(f"[REPO] market_catalog upsert error: {e}")

    def upsert_market_snapshot_focus(self, rows: list[dict[str, Any]]) -> None:
        """Upsert focus snapshots (high-frequency, ~500ms cadence)."""
        if not rows:
            return
        try:
            self.sb.table("market_snapshot_focus").upsert(
                rows, on_conflict="symbol"
            ).execute()
        except Exception as e:
            print(f"[REPO] market_snapshot_focus upsert error: {e}")

    def upsert_market_snapshot_scout(self, rows: list[dict[str, Any]]) -> None:
        """Upsert scout snapshots (low-frequency, ~10s cadence)."""
        if not rows:
            return
        try:
            self.sb.table("market_snapshot_scout").upsert(
                rows, on_conflict="symbol"
            ).execute()
        except Exception as e:
            print(f"[REPO] market_snapshot_scout upsert error: {e}")

    def get_focus_snapshot(self, symbol: str) -> dict[str, Any] | None:
        """Get a single focus snapshot by symbol."""
        try:
            resp = (
                self.sb.table("market_snapshot_focus")
                .select("*")
                .eq("symbol", symbol)
                .maybe_single()
                .execute()
            )
            return resp.data if resp else None
        except Exception:
            return None

    def get_all_focus_snapshots(self) -> list[dict[str, Any]]:
        """Get all focus snapshots."""
        try:
            resp = (
                self.sb.table("market_snapshot_focus")
                .select("*")
                .order("symbol")
                .execute()
            )
            return resp.data or []
        except Exception:
            return []

    # ── Order intents (Phase 2) ──

    def upsert_order_intent(self, intent: dict[str, Any]) -> None:
        """Insert or update an order intent."""
        self.sb.table("order_intents").upsert(
            intent, on_conflict="intent_id"
        ).execute()

    def update_order_intent_status(self, intent_id: str, status: str, **kwargs: Any) -> None:
        """Update the status of an order intent."""
        updates: dict[str, Any] = {"status": status}
        updates.update(kwargs)
        self.sb.table("order_intents").update(updates).eq("intent_id", intent_id).execute()

    # ── Positions (Phase 2) ──

    def upsert_position(self, position: dict[str, Any]) -> None:
        """Upsert a position row (symbol, mode composite key)."""
        self.sb.table("positions").upsert(
            position, on_conflict="symbol,mode"
        ).execute()

    def get_position(self, symbol: str, mode: str) -> dict[str, Any] | None:
        """Get a single position by symbol and mode."""
        try:
            resp = (
                self.sb.table("positions")
                .select("*")
                .eq("symbol", symbol)
                .eq("mode", mode)
                .maybe_single()
                .execute()
            )
            return resp.data if resp else None
        except Exception:
            return None

    def list_positions(self, mode: str) -> list[dict[str, Any]]:
        """List all positions for a mode."""
        try:
            resp = (
                self.sb.table("positions")
                .select("*")
                .eq("mode", mode)
                .gt("qty", 0)
                .execute()
            )
            return resp.data or []
        except Exception:
            return []

    # ── Trade locks (Phase 2) ──

    def acquire_trade_lock(self, symbol: str, mode: str, locked_by: str, ttl_s: int = 30) -> bool:
        """Try to acquire a trade lock. Returns True if lock was acquired."""
        from datetime import timedelta
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_s)
        try:
            # Delete expired locks first
            self.sb.table("trade_locks").delete().lt(
                "expires_at", datetime.now(timezone.utc).isoformat()
            ).execute()
            # Try to insert (will fail if lock exists and not expired)
            self.sb.table("trade_locks").insert({
                "symbol": symbol,
                "mode": mode,
                "locked_by": locked_by,
                "locked_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires.isoformat(),
            }).execute()
            return True
        except Exception:
            return False

    def release_trade_lock(self, symbol: str, mode: str) -> None:
        """Release a trade lock."""
        try:
            self.sb.table("trade_locks").delete().eq(
                "symbol", symbol
            ).eq("mode", mode).execute()
        except Exception:
            pass

    # ── Fee ledger (Phase 3) ──

    def insert_fee_ledger(self, entry: dict[str, Any]) -> None:
        """Insert a fee ledger entry."""
        self.sb.table("fee_ledger").insert(entry).execute()

    def get_cumulative_fees(self, mode: str) -> float:
        """Sum all fees in the fee ledger for a mode."""
        try:
            resp = (
                self.sb.table("fee_ledger")
                .select("fee_usd")
                .eq("mode", mode)
                .execute()
            )
            return sum(float(r.get("fee_usd", 0)) for r in (resp.data or []))
        except Exception:
            return 0.0
