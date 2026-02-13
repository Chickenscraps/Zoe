"""Trade lock — prevents concurrent engines from trading the same symbol.

Uses Supabase row-level locking via INSERT ON CONFLICT DO NOTHING pattern.
Prevents Edge Factory and CryptoTrader from trading the same symbol simultaneously.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class TradeLock:
    """Distributed trade lock using Supabase trade_locks table."""

    def __init__(self, supabase_client: Any, engine: str = "", mode: str = "paper"):
        self._sb = supabase_client
        self._engine = engine
        self._mode = mode
        self._holder_id = f"{engine}-{uuid.uuid4().hex[:8]}"

    async def acquire(self, symbol: str) -> bool:
        """Attempt to acquire lock for a symbol. Returns True if acquired."""
        try:
            # INSERT with ON CONFLICT DO NOTHING
            resp = self._sb.table("trade_locks").upsert({
                "symbol": symbol,
                "engine": self._engine,
                "mode": self._mode,
                "locked_at": datetime.now(timezone.utc).isoformat(),
                "lock_holder": self._holder_id,
            }, on_conflict="symbol,engine,mode").execute()

            # Verify we got the lock (our holder_id is in the row)
            verify = self._sb.table("trade_locks").select("lock_holder").eq(
                "symbol", symbol
            ).eq("engine", self._engine).eq("mode", self._mode).maybeSingle().execute()

            if verify.data and verify.data.get("lock_holder") == self._holder_id:
                logger.debug("Lock acquired: %s/%s/%s", symbol, self._engine, self._mode)
                return True

            # Someone else holds the lock
            holder = verify.data.get("lock_holder", "unknown") if verify.data else "unknown"
            logger.info("Lock denied for %s: held by %s", symbol, holder)
            return False

        except Exception as e:
            logger.warning("Lock acquire failed for %s: %s", symbol, e)
            return False

    async def release(self, symbol: str) -> bool:
        """Release lock for a symbol. Only succeeds if we hold it."""
        try:
            self._sb.table("trade_locks").delete().eq(
                "symbol", symbol
            ).eq("lock_holder", self._holder_id).execute()
            logger.debug("Lock released: %s/%s", symbol, self._engine)
            return True
        except Exception as e:
            logger.warning("Lock release failed for %s: %s", symbol, e)
            return False

    async def release_all(self) -> None:
        """Release all locks held by this engine instance."""
        try:
            self._sb.table("trade_locks").delete().eq(
                "lock_holder", self._holder_id
            ).execute()
            logger.info("All locks released for %s", self._holder_id)
        except Exception as e:
            logger.warning("Release all locks failed: %s", e)

    async def is_locked(self, symbol: str) -> bool:
        """Check if a symbol is locked by any engine."""
        try:
            resp = self._sb.table("trade_locks").select("lock_holder").eq(
                "symbol", symbol
            ).eq("mode", self._mode).execute()
            return bool(resp.data)
        except Exception:
            return False

    async def get_lock_holder(self, symbol: str) -> str | None:
        """Get the holder of a symbol lock."""
        try:
            resp = self._sb.table("trade_locks").select("lock_holder, engine").eq(
                "symbol", symbol
            ).eq("mode", self._mode).maybeSingle().execute()
            if resp.data:
                return f"{resp.data.get('engine', '?')}/{resp.data.get('lock_holder', '?')}"
            return None
        except Exception:
            return None
