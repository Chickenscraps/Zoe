"""Mark-to-market pricing — reads marks from market_snapshot_focus.

Provides a simple interface to get current mark prices for symbols,
with staleness detection and exchange REST fallback.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Consider a focus snapshot stale if older than this many seconds
STALE_THRESHOLD_SEC = 120


class MarkToMarket:
    """Reads mark prices from Supabase focus snapshots."""

    def __init__(self, supabase_client: Any, exchange_client: Any | None = None):
        self._sb = supabase_client
        self._exchange = exchange_client

    async def get_mark(self, symbol: str) -> float:
        """Get current mark price for a single symbol. Returns 0.0 if unavailable."""
        marks = await self.get_marks([symbol])
        return marks.get(symbol, 0.0)

    async def get_marks(self, symbols: list[str]) -> dict[str, float]:
        """Get mark prices for multiple symbols from focus snapshots."""
        if not symbols:
            return {}

        marks: dict[str, float] = {}

        try:
            resp = self._sb.table("market_snapshot_focus").select(
                "symbol, mid, updated_at"
            ).in_("symbol", symbols).execute()

            now = datetime.now(timezone.utc)
            for row in (resp.data or []):
                mid = float(row.get("mid", 0))
                if mid <= 0:
                    continue

                # Check staleness
                updated = row.get("updated_at")
                if updated:
                    try:
                        ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                        age = (now - ts).total_seconds()
                        if age > STALE_THRESHOLD_SEC:
                            logger.debug("Stale mark for %s (%.0fs old)", row["symbol"], age)
                            continue
                    except (ValueError, TypeError):
                        pass

                marks[row["symbol"]] = mid
        except Exception as e:
            logger.warning("Focus mark fetch failed: %s", e)

        # Fallback to exchange for missing
        missing = [s for s in symbols if s not in marks]
        if missing and self._exchange:
            for sym in missing:
                try:
                    data = await self._exchange.get_best_bid_ask(sym)
                    results = data.get("results", [])
                    if results:
                        entry = results[0]
                        bid = float(entry.get("bid", entry.get("bid_price", 0)))
                        ask = float(entry.get("ask", entry.get("ask_price", 0)))
                        if bid > 0 and ask > 0:
                            marks[sym] = (bid + ask) / 2.0
                except Exception:
                    pass

        return marks
