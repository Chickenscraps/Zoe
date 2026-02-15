"""Position Tracker — in-memory + SQLite position state machine.

Tracks positions from entry fill → exit → close with live P&L.

State machine:
  OPEN → EXIT_PENDING → CLOSING → CLOSED

Persists to local_positions table in LocalEventStore.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from services.local_store import LocalEventStore
    from services.crypto_trader.price_cache import PriceCache

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Position lifecycle states."""
    OPEN = "open"                  # Entry filled, no exit started
    EXIT_PENDING = "exit_pending"  # Exit ordered but not yet working
    CLOSING = "closing"            # Exit order working/partially filled
    CLOSED = "closed"              # Fully exited


@dataclass
class Position:
    """Tracked position from entry to exit."""
    id: str
    symbol: str
    side: str                    # "long" or "short"
    entry_price: float
    entry_qty: float
    entry_time: float            # monotonic timestamp
    entry_time_utc: str          # ISO 8601

    # Exit plan
    tp_price: float              # Take-profit target
    sl_price: float              # Stop-loss level
    trailing_sl: float | None = None
    high_water_mark: float = 0.0

    # Exit tracking
    exit_order_id: str | None = None
    exit_price: float | None = None
    exit_qty: float | None = None
    exit_time: float | None = None

    # Status
    status: PositionStatus = PositionStatus.OPEN
    unrealized_pnl: float = 0.0
    realized_pnl: float | None = None

    # Metadata
    entry_order_id: str | None = None
    strategy: str | None = None
    signal_score: float | None = None
    mode: str = "paper"

    @property
    def notional(self) -> float:
        """Current notional value (entry)."""
        return self.entry_price * self.entry_qty

    @property
    def is_open(self) -> bool:
        return self.status in (PositionStatus.OPEN, PositionStatus.EXIT_PENDING, PositionStatus.CLOSING)

    @property
    def age_seconds(self) -> float:
        """Seconds since entry fill."""
        return time.monotonic() - self.entry_time

    @property
    def age_hours(self) -> float:
        return self.age_seconds / 3600

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "entry_qty": self.entry_qty,
            "entry_time_utc": self.entry_time_utc,
            "tp_price": self.tp_price,
            "sl_price": self.sl_price,
            "trailing_sl": self.trailing_sl,
            "high_water_mark": self.high_water_mark,
            "exit_order_id": self.exit_order_id,
            "exit_price": self.exit_price,
            "exit_qty": self.exit_qty,
            "status": self.status.value,
            "unrealized_pnl": round(self.unrealized_pnl, 4),
            "realized_pnl": round(self.realized_pnl, 4) if self.realized_pnl is not None else None,
            "entry_order_id": self.entry_order_id,
            "strategy": self.strategy,
            "signal_score": self.signal_score,
            "mode": self.mode,
        }


class PositionTracker:
    """In-memory position tracker with SQLite persistence.

    Usage:
        tracker = PositionTracker(local_store, mode="live")
        tracker.recover()  # restore from DB on boot

        pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp=72000, sl=67000)
        tracker.update_marks(price_cache)
        tracker.begin_exit(pos.id, exit_order_id="O123")
        tracker.close_position(pos.id, exit_price=72000, realized_pnl=3.0)
    """

    def __init__(
        self,
        local_store: "LocalEventStore | None" = None,
        mode: str = "paper",
    ):
        self._positions: dict[str, Position] = {}  # position_id → Position
        self._store = local_store
        self._mode = mode

    def open_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        avg_price: float,
        tp_price: float,
        sl_price: float,
        entry_order_id: str | None = None,
        strategy: str | None = None,
        signal_score: float | None = None,
        entry_time_utc: str | None = None,
    ) -> Position:
        """Register a new open position after entry fill."""
        pos_id = str(uuid.uuid4())
        from datetime import datetime, timezone
        utc_now = entry_time_utc or datetime.now(timezone.utc).isoformat()

        pos = Position(
            id=pos_id,
            symbol=symbol,
            side=side,
            entry_price=avg_price,
            entry_qty=qty,
            entry_time=time.monotonic(),
            entry_time_utc=utc_now,
            tp_price=tp_price,
            sl_price=sl_price,
            high_water_mark=avg_price,
            entry_order_id=entry_order_id,
            strategy=strategy,
            signal_score=signal_score,
            mode=self._mode,
        )

        self._positions[pos_id] = pos
        self._persist(pos)

        logger.info(
            "Position opened: %s %s %.6f @ $%.2f (TP=$%.2f, SL=$%.2f) [%s]",
            side, symbol, qty, avg_price, tp_price, sl_price, pos_id[:8],
        )
        return pos

    def begin_exit(self, position_id: str, exit_order_id: str) -> None:
        """Mark position as exit-pending (TP/SL order submitted)."""
        pos = self._positions.get(position_id)
        if not pos:
            logger.warning("begin_exit: unknown position %s", position_id)
            return
        if pos.status == PositionStatus.CLOSED:
            return

        pos.status = PositionStatus.EXIT_PENDING
        pos.exit_order_id = exit_order_id
        self._persist(pos)

        logger.info(
            "Position exit pending: %s %s [order=%s]",
            pos.symbol, position_id[:8], exit_order_id[:12],
        )

    def mark_closing(self, position_id: str) -> None:
        """Mark position as actively closing (exit order is working)."""
        pos = self._positions.get(position_id)
        if not pos:
            return
        if pos.status == PositionStatus.CLOSED:
            return
        pos.status = PositionStatus.CLOSING
        self._persist(pos)

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_qty: float | None = None,
        realized_pnl: float | None = None,
    ) -> Position | None:
        """Close a position after exit fill."""
        pos = self._positions.get(position_id)
        if not pos:
            logger.warning("close_position: unknown position %s", position_id)
            return None

        pos.status = PositionStatus.CLOSED
        pos.exit_price = exit_price
        pos.exit_qty = exit_qty or pos.entry_qty
        pos.exit_time = time.monotonic()

        # Compute realized P&L if not provided
        if realized_pnl is not None:
            pos.realized_pnl = realized_pnl
        else:
            if pos.side == "long":
                pos.realized_pnl = (exit_price - pos.entry_price) * pos.entry_qty
            else:
                pos.realized_pnl = (pos.entry_price - exit_price) * pos.entry_qty

        pos.unrealized_pnl = 0.0
        self._persist(pos)

        logger.info(
            "Position closed: %s %s PnL=$%.4f (entry=$%.2f, exit=$%.2f) [%s]",
            pos.side, pos.symbol, pos.realized_pnl, pos.entry_price,
            exit_price, position_id[:8],
        )
        return pos

    def update_marks(self, price_cache: "PriceCache") -> None:
        """Update unrealized P&L for all open positions from live prices."""
        for pos in self._positions.values():
            if not pos.is_open:
                continue

            snap = price_cache.snapshot(pos.symbol)
            mid = snap.get("mid", 0.0)
            if mid <= 0:
                continue

            # Update high water mark (for trailing stop)
            if pos.side == "long":
                pos.high_water_mark = max(pos.high_water_mark, mid)
                pos.unrealized_pnl = (mid - pos.entry_price) * pos.entry_qty
            else:
                pos.high_water_mark = min(pos.high_water_mark, mid) if pos.high_water_mark > 0 else mid
                pos.unrealized_pnl = (pos.entry_price - mid) * pos.entry_qty

    def get_open(self) -> list[Position]:
        """Get all open (non-closed) positions."""
        return [p for p in self._positions.values() if p.is_open]

    def get_all(self) -> list[Position]:
        """Get all positions (including closed)."""
        return list(self._positions.values())

    def get_exposure(self) -> dict[str, float]:
        """Get per-symbol notional exposure for open positions."""
        exposure: dict[str, float] = {}
        for pos in self._positions.values():
            if pos.is_open:
                exposure[pos.symbol] = exposure.get(pos.symbol, 0.0) + pos.notional
        return exposure

    def get_total_exposure(self) -> float:
        """Get total notional exposure across all open positions."""
        return sum(self.get_exposure().values())

    def has_position(self, symbol: str) -> bool:
        """Check if there's an open position for this symbol."""
        return any(
            p.symbol == symbol and p.is_open
            for p in self._positions.values()
        )

    def get_position_by_symbol(self, symbol: str) -> Position | None:
        """Get the open position for a symbol (None if not held)."""
        for p in self._positions.values():
            if p.symbol == symbol and p.is_open:
                return p
        return None

    def position_count(self) -> int:
        """Count of open positions."""
        return sum(1 for p in self._positions.values() if p.is_open)

    def recover(self, local_store: "LocalEventStore | None" = None) -> int:
        """Recover open positions from SQLite on boot.

        Returns count of recovered positions.
        """
        store = local_store or self._store
        if not store:
            return 0

        try:
            rows = store.get_open_positions(self._mode)
        except Exception as e:
            logger.error("Position recovery failed: %s", e)
            return 0

        count = 0
        for row in rows:
            status_str = row.get("status", "open")
            try:
                status = PositionStatus(status_str)
            except ValueError:
                status = PositionStatus.OPEN

            if status == PositionStatus.CLOSED:
                continue

            pos = Position(
                id=row.get("position_id", str(uuid.uuid4())),
                symbol=row.get("symbol", ""),
                side=row.get("side", "long"),
                entry_price=float(row.get("entry_price", 0)),
                entry_qty=float(row.get("qty", 0)),
                entry_time=time.monotonic(),  # approximate
                entry_time_utc=row.get("entry_time", ""),
                tp_price=float(row.get("tp_price", 0)),
                sl_price=float(row.get("sl_price", 0)),
                exit_order_id=row.get("exit_order_id"),
                status=status,
                entry_order_id=row.get("entry_order_id"),
                strategy=row.get("strategy"),
                mode=self._mode,
            )
            self._positions[pos.id] = pos
            count += 1

        if count > 0:
            logger.info("Recovered %d open position(s) from DB", count)
        return count

    def _persist(self, pos: Position) -> None:
        """Write position to SQLite for persistence across restarts."""
        if not self._store:
            return
        try:
            self._store.insert_position({
                "position_id": pos.id,
                "symbol": pos.symbol,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "size_usd": pos.notional,
                "qty": pos.entry_qty,
                "tp_price": pos.tp_price,
                "sl_price": pos.sl_price,
                "exit_price": pos.exit_price,
                "exit_time": pos.exit_time,
                "pnl_usd": pos.realized_pnl,
                "status": pos.status.value,
                "entry_order_id": pos.entry_order_id,
                "exit_order_id": pos.exit_order_id,
                "signal_strength": pos.signal_score,
                "regime": None,
                "mode": pos.mode,
            })
        except Exception as e:
            logger.error("Position persist failed: %s", e)
