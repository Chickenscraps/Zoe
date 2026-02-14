"""Coalescer — per-symbol latest-value buffer with timer-based flush.

Prevents write storms: instead of writing every WS tick to Supabase,
we buffer the latest value per symbol and flush on a timer.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class TickerSnapshot:
    """Latest ticker data for a single symbol."""

    symbol: str
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    spread_pct: float = 0.0
    volume_24h: float = 0.0
    change_24h_pct: float = 0.0
    vwap: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Coalescer:
    """Buffers latest ticker data and flushes on configurable timer.

    Usage:
        coalescer = Coalescer(flush_interval_ms=1000, on_flush=write_to_supabase)
        coalescer.update("BTC-USD", bid=50000, ask=50001, ...)
        # Timer fires every 1s, calls on_flush with all dirty snapshots
    """

    def __init__(
        self,
        flush_interval_ms: int,
        on_flush: Callable[[list[TickerSnapshot]], Awaitable[None]],
        name: str = "coalescer",
    ):
        self.flush_interval_ms = flush_interval_ms
        self.on_flush = on_flush
        self.name = name

        self._buffer: dict[str, TickerSnapshot] = {}
        self._dirty: set[str] = set()
        self._task: asyncio.Task | None = None
        self._running = False

        # Stats
        self._total_updates = 0
        self._total_flushes = 0

    def update(self, symbol: str, **kwargs: Any) -> None:
        """Update the latest snapshot for a symbol. Only dirty symbols get flushed."""
        snap = self._buffer.get(symbol)
        if snap is None:
            snap = TickerSnapshot(symbol=symbol)
            self._buffer[symbol] = snap

        for key, value in kwargs.items():
            if hasattr(snap, key):
                setattr(snap, key, value)

        # Compute derived fields
        if snap.bid > 0 and snap.ask > 0:
            snap.mid = (snap.bid + snap.ask) / 2
            snap.spread_pct = (snap.ask - snap.bid) / snap.mid * 100 if snap.mid > 0 else 0

        snap.updated_at = datetime.now(timezone.utc)
        self._dirty.add(symbol)
        self._total_updates += 1

    def get(self, symbol: str) -> TickerSnapshot | None:
        """Get the latest buffered snapshot for a symbol."""
        return self._buffer.get(symbol)

    def get_all(self) -> dict[str, TickerSnapshot]:
        """Get all buffered snapshots."""
        return dict(self._buffer)

    async def start(self) -> None:
        """Start the periodic flush timer."""
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("%s: started (flush every %dms)", self.name, self.flush_interval_ms)

    async def stop(self) -> None:
        """Stop the flush timer and do a final flush."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._flush()

    async def _flush_loop(self) -> None:
        """Background loop that flushes dirty symbols periodically."""
        interval = self.flush_interval_ms / 1000.0
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("%s: flush error: %s", self.name, e)

    async def _flush(self) -> None:
        """Flush all dirty symbols to the callback."""
        if not self._dirty:
            return

        # Snapshot and clear dirty set atomically
        dirty_symbols = list(self._dirty)
        self._dirty.clear()

        snapshots = [self._buffer[s] for s in dirty_symbols if s in self._buffer]
        if not snapshots:
            return

        try:
            await self.on_flush(snapshots)
            self._total_flushes += 1
        except Exception as e:
            logger.warning("%s: flush callback error (%d symbols): %s", self.name, len(snapshots), e)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total_updates": self._total_updates,
            "total_flushes": self._total_flushes,
            "buffered_symbols": len(self._buffer),
            "dirty_symbols": len(self._dirty),
        }
