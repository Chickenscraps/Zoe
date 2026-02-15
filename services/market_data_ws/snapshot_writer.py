"""Snapshot Writer — coalesced batch upserts to Supabase.

Avoids write storms by batching upserts and using coalesced data
from the Coalescer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .coalescer import TickerSnapshot

logger = logging.getLogger(__name__)


class SnapshotWriter:
    """Writes ticker snapshots to Supabase market_snapshot_* tables."""

    def __init__(self, supabase: Any, chunk_size: int = 50):
        self.sb = supabase
        self.chunk_size = chunk_size
        self._focus_writes = 0
        self._scout_writes = 0

    async def write_focus(self, snapshots: list[TickerSnapshot]) -> None:
        """Upsert snapshots to market_snapshot_focus."""
        if not snapshots:
            return

        rows = [
            {
                "symbol": s.symbol,
                "bid": float(s.bid),
                "ask": float(s.ask),
                "mid": float(s.mid),
                "spread_pct": float(s.spread_pct),
                "volume_24h": float(s.volume_24h),
                "change_24h_pct": float(s.change_24h_pct),
                "vwap": float(s.vwap),
                "high_24h": float(s.high_24h),
                "low_24h": float(s.low_24h),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in snapshots
        ]

        try:
            for i in range(0, len(rows), self.chunk_size):
                chunk = rows[i : i + self.chunk_size]
                self.sb.table("market_snapshot_focus").upsert(
                    chunk, on_conflict="symbol"
                ).execute()
            self._focus_writes += len(rows)
        except Exception as e:
            logger.warning("Focus snapshot write failed (%d rows): %s", len(rows), e)

    async def write_scout(self, snapshots: list[TickerSnapshot]) -> None:
        """Upsert snapshots to market_snapshot_scout."""
        if not snapshots:
            return

        rows = [
            {
                "symbol": s.symbol,
                "bid": float(s.bid),
                "ask": float(s.ask),
                "mid": float(s.mid),
                "spread_pct": float(s.spread_pct),
                "volume_24h": float(s.volume_24h),
                "change_24h_pct": float(s.change_24h_pct),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in snapshots
        ]

        try:
            for i in range(0, len(rows), self.chunk_size):
                chunk = rows[i : i + self.chunk_size]
                self.sb.table("market_snapshot_scout").upsert(
                    chunk, on_conflict="symbol"
                ).execute()
            self._scout_writes += len(rows)
        except Exception as e:
            logger.warning("Scout snapshot write failed (%d rows): %s", len(rows), e)

    async def write_sparkline(self, symbol: str, price: float) -> None:
        """Insert a sparkline point."""
        try:
            self.sb.table("market_sparkline_points").insert({
                "symbol": symbol,
                "ts": datetime.now(timezone.utc).isoformat(),
                "price": float(price),
            }).execute()
        except Exception as e:
            # Likely duplicate key on same bucket — ignore
            if "duplicate" not in str(e).lower():
                logger.warning("Sparkline write failed for %s: %s", symbol, e)

    async def write_mover(
        self,
        symbol: str,
        event_type: str,
        magnitude: float,
        direction: str = "up",
        metadata: dict | None = None,
    ) -> None:
        """Insert a mover event."""
        try:
            self.sb.table("mover_events").insert({
                "symbol": symbol,
                "event_type": event_type,
                "magnitude": float(magnitude),
                "direction": direction,
                "metadata": metadata or {},
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.info("MOVER: %s %s %.2f%% %s", event_type, symbol, magnitude, direction)
        except Exception as e:
            logger.warning("Mover event write failed for %s: %s", symbol, e)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "focus_writes": self._focus_writes,
            "scout_writes": self._scout_writes,
        }
