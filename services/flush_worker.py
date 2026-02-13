"""
Flush Worker — Periodically batch-flushes local events to Supabase.

Runs as a background asyncio task alongside the trading loop.
Does NOT block trading — failures are logged and retried.

Usage:
    worker = FlushWorker(local_store, supabase_client, mode="live")
    asyncio.create_task(worker.run_forever())
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

from .local_store import LocalEventStore

logger = logging.getLogger(__name__)

# Event subtypes that trigger immediate flush
CRITICAL_SUBTYPES = frozenset({
    "BUY_FILLED", "SELL_FILLED", "PNL_REALIZED",
    "TRADING_HALTED", "KILL_SWITCH", "RECONCILIATION_MISMATCH",
})


class FlushWorker:
    """Non-blocking flush loop: local SQLite → Supabase zoe_events."""

    def __init__(
        self,
        store: LocalEventStore,
        supabase_client: Any,
        mode: str = "live",
    ) -> None:
        self.store = store
        self.sb = supabase_client
        self.mode = mode

        # Config dials (overridable via env)
        self.flush_interval_active = int(os.getenv("FLUSH_INTERVAL_ACTIVE", "15"))
        self.flush_interval_offhours = int(os.getenv("FLUSH_INTERVAL_OFFHOURS", "120"))
        self.flush_batch_size = int(os.getenv("FLUSH_BATCH_SIZE", "500"))
        self.flush_critical_immediate = os.getenv("FLUSH_CRITICAL_IMMEDIATE", "true").lower() == "true"

        self._retry_delay = 5  # Initial retry delay (seconds)
        self._max_retry_delay = 300  # Max 5 minutes between retries
        self._consecutive_failures = 0

    def get_flush_interval(self) -> int:
        """Return active or offhours interval based on time of day."""
        hour = datetime.now(timezone.utc).hour
        # Consider 14:00-04:00 UTC as "active hours" (crypto markets are 24/7,
        # but US hours 9am-11pm ET roughly maps to 14:00-04:00 UTC)
        if 4 <= hour < 14:
            return self.flush_interval_offhours
        return self.flush_interval_active

    async def flush_batch(self) -> int:
        """
        Flush unflushed local events to Supabase.
        Returns number of events flushed.
        """
        events = self.store.get_unflushed(limit=self.flush_batch_size)
        if not events:
            return 0

        # Prepare rows for Supabase upsert
        rows = []
        for e in events:
            rows.append({
                "id": e["id"],
                "ts": e["ts"],
                "mode": e["mode"],
                "seq": e["seq"],
                "source": e["source"],
                "type": e["type"],
                "subtype": e["subtype"],
                "symbol": e["symbol"],
                "severity": e["severity"],
                "body": e["body"],
                "meta": e["meta"],
                "idempotency_key": e["idempotency_key"],
                "created_at": e["ts"],
            })

        try:
            # Bulk upsert — idempotency_key prevents duplicates
            self.sb.table("zoe_events").upsert(
                rows, on_conflict="idempotency_key"
            ).execute()

            # Mark as flushed
            event_ids = [e["id"] for e in events]
            self.store.mark_flushed(event_ids)

            # Update health timestamp
            try:
                self.sb.table("zoe_health").upsert({
                    "mode": self.mode,
                    "last_flush_ts": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
            except Exception:
                pass  # Non-critical

            # Log success
            last_seq = events[-1]["seq"]
            self.store.log_flush(self.mode, len(events), last_seq, "ok")
            self._consecutive_failures = 0
            self._retry_delay = 5  # Reset backoff

            logger.info(
                "Flushed %d events to Supabase (last_seq=%d)",
                len(events), last_seq,
            )
            return len(events)

        except Exception as e:
            self._consecutive_failures += 1
            last_seq = events[-1]["seq"] if events else 0
            self.store.log_flush(
                self.mode, len(events), last_seq, "error", str(e)
            )
            logger.warning(
                "Flush failed (attempt %d): %s",
                self._consecutive_failures, e,
            )

            # Exponential backoff
            self._retry_delay = min(
                self._retry_delay * 2,
                self._max_retry_delay,
            )
            return 0

    async def on_critical_event(self, event: dict[str, Any]) -> None:
        """Immediately flush if event is critical (e.g. BUY_FILLED)."""
        if self.flush_critical_immediate and event.get("subtype") in CRITICAL_SUBTYPES:
            logger.info("Critical event %s — immediate flush", event["subtype"])
            await self.flush_batch()

    async def run_forever(self) -> None:
        """Main flush loop. Runs until cancelled."""
        logger.info(
            "FlushWorker started (mode=%s, active=%ds, offhours=%ds, batch=%d)",
            self.mode,
            self.flush_interval_active,
            self.flush_interval_offhours,
            self.flush_batch_size,
        )

        while True:
            try:
                flushed = await self.flush_batch()

                # If we flushed a full batch, there might be more — loop immediately
                if flushed >= self.flush_batch_size:
                    continue

                # Otherwise wait for next interval
                interval = self.get_flush_interval()
                if self._consecutive_failures > 0:
                    interval = max(interval, self._retry_delay)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                # Final flush on shutdown
                logger.info("FlushWorker shutting down — final flush...")
                try:
                    await self.flush_batch()
                except Exception:
                    pass
                break
            except Exception as e:
                logger.error("FlushWorker error: %s", e)
                await asyncio.sleep(self._retry_delay)
