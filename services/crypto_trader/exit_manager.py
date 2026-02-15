"""Exit Manager — automated take-profit, stop-loss, trailing stops, and time stops.

After an entry fill, the ExitManager:
  1. Places a limit sell at the TP price
  2. Monitors SL in-process (checked every tick, ~5s)
  3. Tightens trailing stop once position is profitable
  4. Forces market exit after time_stop_hours

All exit orders use the same OrderManager.submit_intent() flow
with TTL-based repositioning for unfilled limit orders.

SL is monitored in-process (not a resting exchange order) for flexibility
and to avoid wick-hunting. Reacts within 1 tick (~5 seconds).
"""
from __future__ import annotations

import logging
import time
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from services.crypto_trader.order_manager import OrderManager
    from services.crypto_trader.price_cache import PriceCache
    from services.crypto_trader.indicators import IndicatorEngine
    from services.crypto_trader.position_tracker import PositionTracker, Position
    from services.risk.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.yaml"


@dataclass
class ExitPolicy:
    """Exit strategy parameters."""
    tp_pct: float = 0.045           # 4.5% take-profit
    sl_atr_mult: float = 1.5        # SL = entry ± 1.5 × ATR
    sl_hard_pct: float = 0.03       # 3% hard stop-loss floor
    time_stop_hours: float = 12.0   # Force exit after 12 hours
    trailing_activate_pct: float = 0.02  # Start trailing after 2% profit
    trailing_step_pct: float = 0.005     # Trail 0.5% below high-water

    @classmethod
    def from_config(cls) -> "ExitPolicy":
        """Load exit policy from config.yaml."""
        try:
            with open(_CONFIG_PATH, "r") as f:
                cfg = yaml.safe_load(f) or {}
            bounce_exec = cfg.get("bounce", {}).get("execution", {})
            return cls(
                tp_pct=bounce_exec.get("tp_pct", 0.045),
                sl_atr_mult=bounce_exec.get("sl_atr_mult", 1.5),
                sl_hard_pct=bounce_exec.get("sl_hard_pct", 0.03),
                time_stop_hours=bounce_exec.get("time_stop_hours", 12.0),
                trailing_activate_pct=bounce_exec.get("trailing_activate_pct", 0.02),
                trailing_step_pct=bounce_exec.get("trailing_step_pct", 0.005),
            )
        except Exception:
            return cls()


@dataclass
class ManagedExit:
    """Tracks the exit state for a single position."""
    position_id: str
    symbol: str
    side: str                    # "long" or "short"
    entry_price: float
    entry_qty: float
    entry_time: float            # monotonic

    # Exit levels
    tp_price: float
    sl_price: float
    trailing_sl: float | None = None
    high_water_mark: float = 0.0

    # Exit order tracking
    tp_order_id: str | None = None
    sl_order_id: str | None = None       # only used when SL fires
    tp_order_status: str = "pending"     # pending, placed, filled, cancelled
    sl_triggered: bool = False
    exit_reason: str | None = None

    @property
    def age_hours(self) -> float:
        return (time.monotonic() - self.entry_time) / 3600


class ExitManager:
    """Manages exit orders for all open positions.

    Usage:
        exit_mgr = ExitManager(order_mgr, price_cache, indicator_engine,
                               policy, position_tracker)

        # After entry fill:
        await exit_mgr.on_entry_fill(position)

        # Every tick (5s):
        await exit_mgr.tick()

        # After exit fill:
        exit_mgr.on_exit_fill(symbol, qty, price, order_id)
    """

    def __init__(
        self,
        order_manager: "OrderManager",
        price_cache: "PriceCache",
        indicator_engine: "IndicatorEngine | None" = None,
        policy: ExitPolicy | None = None,
        position_tracker: "PositionTracker | None" = None,
        circuit_breaker: "CircuitBreaker | None" = None,
        mode: str = "paper",
    ):
        self._order_mgr = order_manager
        self._price_cache = price_cache
        self._indicator_engine = indicator_engine
        self._policy = policy or ExitPolicy()
        self._tracker = position_tracker
        self._breaker = circuit_breaker
        self._mode = mode

        # Active exits keyed by position_id
        self._exits: dict[str, ManagedExit] = {}

        # Map exit_order_id → position_id for fill routing
        self._order_to_position: dict[str, str] = {}

    # ── Entry fill handler ──────────────────────────────────────────

    async def on_entry_fill(self, position: "Position") -> None:
        """Called after an entry order fills. Computes TP/SL and places TP order."""
        entry = position.entry_price
        qty = position.entry_qty
        side = position.side

        # Compute TP price
        if side == "long":
            tp_price = round(entry * (1 + self._policy.tp_pct), 8)
        else:
            tp_price = round(entry * (1 - self._policy.tp_pct), 8)

        # Compute SL price from ATR (if available) or hard percentage
        sl_price = self._compute_sl(position.symbol, entry, side)

        managed = ManagedExit(
            position_id=position.id,
            symbol=position.symbol,
            side=side,
            entry_price=entry,
            entry_qty=qty,
            entry_time=position.entry_time,
            tp_price=tp_price,
            sl_price=sl_price,
            high_water_mark=entry,
        )
        self._exits[position.id] = managed

        # Update position tracker with computed levels
        if self._tracker:
            position.tp_price = tp_price
            position.sl_price = sl_price

        # Place TP limit order
        await self._place_tp_order(managed)

        logger.info(
            "Exit plan set: %s %s entry=$%.2f TP=$%.2f SL=$%.2f [%s]",
            side, position.symbol, entry, tp_price, sl_price,
            position.id[:8],
        )

    # ── Tick — called every order management cycle (~5s) ────────────

    async def tick(self) -> None:
        """Check all managed exits for SL triggers, time stops, trailing updates."""
        for pos_id in list(self._exits.keys()):
            managed = self._exits.get(pos_id)
            if not managed:
                continue

            # Skip if already fully exited
            if managed.exit_reason is not None and managed.sl_triggered:
                continue

            snap = self._price_cache.snapshot(managed.symbol)
            mid = snap.get("mid", 0.0)
            if mid <= 0:
                continue

            # 1. Time stop check
            if managed.age_hours >= self._policy.time_stop_hours:
                await self._execute_time_stop(managed, mid)
                continue

            # 2. Update high water mark and trailing stop
            self._update_trailing(managed, mid)

            # 3. SL trigger check (in-process monitoring)
            effective_sl = managed.trailing_sl or managed.sl_price
            sl_hit = False
            if managed.side == "long":
                sl_hit = mid <= effective_sl
            else:
                sl_hit = mid >= effective_sl

            if sl_hit and not managed.sl_triggered:
                await self._execute_sl(managed, mid, effective_sl)
                continue

            # 4. Re-place TP order if cancelled/exhausted
            if managed.tp_order_status == "cancelled" and not managed.sl_triggered:
                await self._place_tp_order(managed)

    # ── Exit fill handler ───────────────────────────────────────────

    def on_exit_fill(
        self,
        symbol: str,
        qty: float,
        price: float,
        order_id: str,
    ) -> str | None:
        """Called when an exit order fills. Returns position_id if matched.

        Returns position_id for the caller to close in PositionTracker.
        """
        pos_id = self._order_to_position.get(order_id)
        if not pos_id:
            # Try to find by symbol (fallback)
            for pid, managed in self._exits.items():
                if managed.symbol == symbol and not managed.exit_reason:
                    pos_id = pid
                    break

        if not pos_id:
            logger.warning("Exit fill for unknown order %s (%s)", order_id, symbol)
            return None

        managed = self._exits.get(pos_id)
        if not managed:
            return pos_id

        # Determine exit reason
        if managed.sl_triggered:
            reason = "stop_loss"
        elif order_id == managed.tp_order_id:
            reason = "take_profit"
        else:
            reason = "exit_fill"

        managed.exit_reason = reason

        # Compute realized P&L
        if managed.side == "long":
            pnl = (price - managed.entry_price) * qty
        else:
            pnl = (managed.entry_price - price) * qty

        # Feed circuit breaker
        if self._breaker:
            self._breaker.record_trade_result(pnl, managed.symbol)

        # Close in position tracker
        if self._tracker:
            self._tracker.close_position(pos_id, exit_price=price, realized_pnl=pnl)

        # Record cooldown in indicator engine
        if self._indicator_engine:
            self._indicator_engine.record_trade(managed.symbol, managed.side)

        logger.info(
            "Exit filled: %s %s @ $%.2f PnL=$%.4f reason=%s [%s]",
            managed.side, managed.symbol, price, pnl, reason,
            pos_id[:8],
        )

        # Clean up
        self._cleanup_exit(pos_id)
        return pos_id

    def on_tp_order_cancelled(self, order_id: str) -> None:
        """Called when a TP order is cancelled/exhausted (max reprices)."""
        pos_id = self._order_to_position.get(order_id)
        if not pos_id:
            return
        managed = self._exits.get(pos_id)
        if managed:
            managed.tp_order_status = "cancelled"
            managed.tp_order_id = None
            logger.info(
                "TP order cancelled for %s, will re-place on next tick [%s]",
                managed.symbol, pos_id[:8],
            )

    # ── Query methods ───────────────────────────────────────────────

    def get_managed_exits(self) -> list[ManagedExit]:
        """Get all currently managed exits."""
        return list(self._exits.values())

    def has_exit(self, position_id: str) -> bool:
        """Check if an exit is being managed for this position."""
        return position_id in self._exits

    def is_exit_order(self, order_id: str) -> bool:
        """Check if an order_id belongs to an exit order."""
        return order_id in self._order_to_position

    def get_position_for_order(self, order_id: str) -> str | None:
        """Get position_id for an exit order_id."""
        return self._order_to_position.get(order_id)

    @property
    def active_exit_count(self) -> int:
        """Count of positions with active exit management."""
        return sum(1 for m in self._exits.values() if m.exit_reason is None)

    # ── Internal methods ────────────────────────────────────────────

    def _compute_sl(self, symbol: str, entry_price: float, side: str) -> float:
        """Compute stop-loss price using ATR (preferred) or hard percentage."""
        atr_price = None

        # Try ATR-based SL
        if self._indicator_engine:
            snap = self._indicator_engine.snapshot(symbol)
            if snap and snap.is_valid() and snap.atr > 0:
                atr_distance = snap.atr * self._policy.sl_atr_mult
                if side == "long":
                    atr_price = entry_price - atr_distance
                else:
                    atr_price = entry_price + atr_distance

        # Hard percentage SL
        if side == "long":
            hard_sl = entry_price * (1 - self._policy.sl_hard_pct)
        else:
            hard_sl = entry_price * (1 + self._policy.sl_hard_pct)

        # Use ATR-based if available and tighter than hard stop
        if atr_price is not None:
            if side == "long":
                # For long: SL should be below entry. Use whichever is closer (higher).
                sl = max(atr_price, hard_sl)
            else:
                # For short: SL should be above entry. Use whichever is closer (lower).
                sl = min(atr_price, hard_sl)
        else:
            sl = hard_sl

        return round(sl, 8)

    def _update_trailing(self, managed: ManagedExit, mid: float) -> None:
        """Update high-water mark and trailing stop."""
        if managed.side == "long":
            managed.high_water_mark = max(managed.high_water_mark, mid)

            # Check if trailing stop should activate
            profit_pct = (managed.high_water_mark - managed.entry_price) / managed.entry_price
            if profit_pct >= self._policy.trailing_activate_pct:
                trailing = managed.high_water_mark * (1 - self._policy.trailing_step_pct)
                # Only tighten, never loosen
                if managed.trailing_sl is None or trailing > managed.trailing_sl:
                    old = managed.trailing_sl
                    managed.trailing_sl = round(trailing, 8)
                    if old is None:
                        logger.info(
                            "Trailing stop activated: %s @ $%.2f (hwm=$%.2f, +%.1f%%)",
                            managed.symbol, managed.trailing_sl,
                            managed.high_water_mark, profit_pct * 100,
                        )
        else:
            # Short position
            if managed.high_water_mark <= 0:
                managed.high_water_mark = mid
            else:
                managed.high_water_mark = min(managed.high_water_mark, mid)

            profit_pct = (managed.entry_price - managed.high_water_mark) / managed.entry_price
            if profit_pct >= self._policy.trailing_activate_pct:
                trailing = managed.high_water_mark * (1 + self._policy.trailing_step_pct)
                if managed.trailing_sl is None or trailing < managed.trailing_sl:
                    managed.trailing_sl = round(trailing, 8)

    async def _place_tp_order(self, managed: ManagedExit) -> None:
        """Place (or re-place) the take-profit limit order."""
        try:
            exit_side = "sell" if managed.side == "long" else "buy"
            intent_id = await self._order_mgr.submit_intent(
                symbol=managed.symbol,
                side=exit_side,
                notional=0.0,  # Use qty instead
                qty=managed.entry_qty,
                purpose="exit",
                strategy="take_profit",
                order_type="limit",
                limit_price=managed.tp_price,
            )

            # The intent_id is the group; we need the actual order_id
            # OrderManager tracks this internally. We use intent_id for routing.
            managed.tp_order_id = intent_id
            managed.tp_order_status = "placed"
            self._order_to_position[intent_id] = managed.position_id

            if self._tracker:
                self._tracker.begin_exit(managed.position_id, intent_id)

            logger.info(
                "TP order placed: %s %s @ $%.2f (qty=%.6f) [%s]",
                exit_side, managed.symbol, managed.tp_price,
                managed.entry_qty, managed.position_id[:8],
            )
        except Exception as e:
            logger.error("Failed to place TP order for %s: %s", managed.symbol, e)
            managed.tp_order_status = "cancelled"

    async def _execute_sl(
        self,
        managed: ManagedExit,
        current_mid: float,
        effective_sl: float,
    ) -> None:
        """Execute stop-loss: cancel TP + submit market sell."""
        managed.sl_triggered = True
        reason = "trailing_stop" if managed.trailing_sl and effective_sl == managed.trailing_sl else "stop_loss"

        logger.warning(
            "SL TRIGGERED: %s %s mid=$%.2f <= SL=$%.2f (%s) [%s]",
            managed.side, managed.symbol, current_mid, effective_sl,
            reason, managed.position_id[:8],
        )

        # Cancel the TP order if it exists
        if managed.tp_order_id:
            try:
                await self._order_mgr.cancel_order(managed.tp_order_id, reason="sl_triggered")
            except Exception as e:
                logger.error("Failed to cancel TP order on SL: %s", e)

        # Submit market exit
        try:
            exit_side = "sell" if managed.side == "long" else "buy"
            intent_id = await self._order_mgr.submit_intent(
                symbol=managed.symbol,
                side=exit_side,
                notional=0.0,
                qty=managed.entry_qty,
                purpose="exit",
                strategy=reason,
                order_type="market",
            )
            managed.sl_order_id = intent_id
            self._order_to_position[intent_id] = managed.position_id

            if self._tracker:
                self._tracker.mark_closing(managed.position_id)

        except Exception as e:
            logger.error("Failed to submit SL market order for %s: %s", managed.symbol, e)

    async def _execute_time_stop(self, managed: ManagedExit, current_mid: float) -> None:
        """Force exit after max hold time."""
        if managed.sl_triggered or managed.exit_reason:
            return

        managed.sl_triggered = True  # prevent re-entry

        logger.warning(
            "TIME STOP: %s %s held %.1fh (max=%.1fh) mid=$%.2f [%s]",
            managed.side, managed.symbol, managed.age_hours,
            self._policy.time_stop_hours, current_mid,
            managed.position_id[:8],
        )

        # Cancel TP order
        if managed.tp_order_id:
            try:
                await self._order_mgr.cancel_order(managed.tp_order_id, reason="time_stop")
            except Exception:
                pass

        # Submit market exit
        try:
            exit_side = "sell" if managed.side == "long" else "buy"
            intent_id = await self._order_mgr.submit_intent(
                symbol=managed.symbol,
                side=exit_side,
                notional=0.0,
                qty=managed.entry_qty,
                purpose="exit",
                strategy="time_stop",
                order_type="market",
            )
            managed.sl_order_id = intent_id
            self._order_to_position[intent_id] = managed.position_id

            if self._tracker:
                self._tracker.mark_closing(managed.position_id)

        except Exception as e:
            logger.error("Failed to submit time-stop order for %s: %s", managed.symbol, e)

    def _cleanup_exit(self, position_id: str) -> None:
        """Remove exit tracking for a closed position."""
        managed = self._exits.pop(position_id, None)
        if managed:
            # Clean up order → position mappings
            for oid in (managed.tp_order_id, managed.sl_order_id):
                if oid:
                    self._order_to_position.pop(oid, None)

    def recover_from_tracker(self, tracker: "PositionTracker") -> int:
        """On boot, set up exit management for recovered open positions.

        Creates ManagedExit entries for positions that have TP/SL levels
        but no active exit orders (orders will be re-placed on next tick).

        Returns count of positions recovered.
        """
        count = 0
        for pos in tracker.get_open():
            if pos.id in self._exits:
                continue  # already managed

            managed = ManagedExit(
                position_id=pos.id,
                symbol=pos.symbol,
                side=pos.side,
                entry_price=pos.entry_price,
                entry_qty=pos.entry_qty,
                entry_time=pos.entry_time,
                tp_price=pos.tp_price,
                sl_price=pos.sl_price,
                high_water_mark=pos.high_water_mark,
                trailing_sl=pos.trailing_sl,
                # TP order will be re-placed on next tick (status=cancelled)
                tp_order_status="cancelled",
            )
            self._exits[pos.id] = managed
            count += 1

        if count > 0:
            logger.info("Recovered exit management for %d position(s)", count)
        return count
