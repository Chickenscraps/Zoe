from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .config import CONFIRM_PHRASE, EdgeFactoryConfig
from .models import EdgePosition, Signal
from .repository import FeatureRepository

if TYPE_CHECKING:
    from .execution_policy import ExecutionPolicyEngine
    from .order_manager import OrderManager
    from .quote_model import QuoteModel

logger = logging.getLogger(__name__)


class LiveExecutor:
    """
    Production executor bridging to existing RobinhoodCryptoClient.

    V1 behavior (no optional params):
    - Places LIMIT orders at bid price
    - 60-second timeout: cancel if unfilled
    - Market sell for exits

    V2 behavior (with quote_model + execution_policy + order_manager):
    - Smart pricing via ExecutionPolicyEngine (PASSIVE/NORMAL/PANIC_EXIT)
    - Cancel/replace loops via OrderManager
    - Slippage tracking and safety gates
    - Falls back to V1 behavior if any optional component is None
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        repository: FeatureRepository,
        rh_client: object,  # RobinhoodCryptoClient
        quote_model: QuoteModel | None = None,
        execution_policy: ExecutionPolicyEngine | None = None,
        order_manager: OrderManager | None = None,
    ):
        self.config = config
        self.repo = repository
        self.rh = rh_client
        self.quote_model = quote_model
        self.execution_policy = execution_policy
        self.order_manager = order_manager
        self._verify_live_mode()

    @property
    def _has_v2(self) -> bool:
        """True if all V2 execution quality components are available."""
        return (
            self.quote_model is not None
            and self.execution_policy is not None
            and self.order_manager is not None
        )

    def _verify_live_mode(self) -> None:
        if not self.config.is_live():
            raise RuntimeError("LiveExecutor requires EDGE_FACTORY_MODE=live")

    async def submit_entry(
        self,
        signal: Signal,
        size_usd: float,
        limit_price: float,
        tp_price: float,
        sl_price: float,
    ) -> str:
        """
        Submit limit buy via Robinhood API.

        V2 path: uses QuoteModel + ExecutionPolicy + OrderManager
        V1 fallback: direct limit at bid with simple poll
        """
        position_id = str(uuid.uuid4())

        if self._has_v2:
            return await self._submit_entry_v2(
                signal, size_usd, limit_price, tp_price, sl_price, position_id
            )

        return await self._submit_entry_v1(
            signal, size_usd, limit_price, tp_price, sl_price, position_id
        )

    async def _submit_entry_v2(
        self,
        signal: Signal,
        size_usd: float,
        limit_price: float,
        tp_price: float,
        sl_price: float,
        position_id: str,
    ) -> str:
        """V2 entry with execution quality layer."""
        assert self.quote_model is not None
        assert self.execution_policy is not None
        assert self.order_manager is not None

        try:
            # Refresh quote
            quote = await self.quote_model.refresh(signal.symbol)

            # Safety gate: spread too wide
            if quote.spread_pct > self.config.max_spread_pct_entry:
                logger.warning(
                    "ENTRY BLOCKED: %s spread %.4f%% > %.4f%% max",
                    signal.symbol, quote.spread_pct * 100, self.config.max_spread_pct_entry * 100,
                )
                return position_id

            # Safety gate: avg slippage too high
            slip_ok, avg_slip = self.order_manager.check_slippage_gate()
            if not slip_ok:
                logger.warning(
                    "ENTRY BLOCKED: avg slippage %.1fbps > %.1fbps max",
                    avg_slip, self.config.max_avg_slippage_bps,
                )
                return position_id

            # Choose execution mode
            mode = self.execution_policy.choose_entry_mode(
                signal.strength, quote.spread_pct
            )
            params = self.execution_policy.compute_entry_params(quote, mode)

            # Execute order with cancel/replace lifecycle
            ticket = await self.order_manager.execute(
                symbol=signal.symbol,
                side="buy",
                size_usd=size_usd,
                params=params,
                reference_mid=quote.mid,
            )

            if ticket.status == "filled" and ticket.fill_price:
                position = EdgePosition(
                    symbol=signal.symbol,
                    side="buy",
                    entry_price=ticket.fill_price,
                    entry_time=datetime.now(timezone.utc),
                    size_usd=size_usd,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    status="open",
                    signal_id=signal.signal_id,
                    order_id=ticket.order_id,
                    position_id=position_id,
                )
                self.repo.insert_position(position)
                logger.info(
                    "LIVE ENTRY FILLED (V2): %s @ %.4f (mode=%s)",
                    signal.symbol, ticket.fill_price, mode.value,
                )
            else:
                # Record failed attempt
                position = EdgePosition(
                    symbol=signal.symbol,
                    side="buy",
                    entry_price=0.0,
                    entry_time=datetime.now(timezone.utc),
                    size_usd=0.0,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    status="closed_timeout",
                    signal_id=signal.signal_id,
                    order_id=ticket.order_id,
                    position_id=position_id,
                )
                self.repo.insert_position(position)

        except Exception as e:
            logger.error("LIVE ENTRY FAILED (V2): %s - %s", signal.symbol, e)
            raise

        return position_id

    async def _submit_entry_v1(
        self,
        signal: Signal,
        size_usd: float,
        limit_price: float,
        tp_price: float,
        sl_price: float,
        position_id: str,
    ) -> str:
        """V1 entry: original simple limit order + poll."""
        client_order_id = f"ef-{signal.symbol.lower()}-{position_id[:8]}"

        try:
            order = await self.rh.place_order(
                symbol=signal.symbol,
                side="buy",
                order_type="limit",
                client_order_id=client_order_id,
                notional=size_usd,
                limit_price=limit_price,
            )

            order_id = order.get("id", client_order_id)
            logger.info(
                "LIVE ENTRY SUBMITTED: %s $%.2f @ limit %.4f (order=%s)",
                signal.symbol, size_usd, limit_price, order_id,
            )

            filled = await self._wait_for_fill(order_id)

            if filled:
                fill_price = filled.get("price", limit_price)
                position = EdgePosition(
                    symbol=signal.symbol,
                    side="buy",
                    entry_price=float(fill_price),
                    entry_time=datetime.now(timezone.utc),
                    size_usd=size_usd,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    status="open",
                    signal_id=signal.signal_id,
                    order_id=order_id,
                    position_id=position_id,
                )
                self.repo.insert_position(position)
                logger.info("LIVE ENTRY FILLED: %s @ %.4f", signal.symbol, float(fill_price))
            else:
                logger.info("LIVE ENTRY TIMEOUT: %s - cancelling order %s", signal.symbol, order_id)
                position = EdgePosition(
                    symbol=signal.symbol,
                    side="buy",
                    entry_price=0.0,
                    entry_time=datetime.now(timezone.utc),
                    size_usd=0.0,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    status="closed_timeout",
                    signal_id=signal.signal_id,
                    order_id=order_id,
                    position_id=position_id,
                )
                self.repo.insert_position(position)

        except Exception as e:
            logger.error("LIVE ENTRY FAILED: %s - %s", signal.symbol, e)
            raise

        return position_id

    async def _wait_for_fill(self, order_id: str) -> dict | None:
        """Poll order status until filled or timeout (V1 path)."""
        timeout = self.config.limit_order_timeout_sec
        poll_interval = 5
        elapsed = 0

        while elapsed < timeout:
            try:
                order = await self.rh.get_order(order_id)
                status = order.get("status", "")

                if status == "filled":
                    fills = await self.rh.get_order_fills(order_id)
                    fill_list = fills.get("results", [])
                    if fill_list:
                        return fill_list[0]
                    return {"price": order.get("price", 0)}

                if status in {"canceled", "rejected", "failed"}:
                    logger.warning("Order %s: %s", order_id, status)
                    return None

            except Exception as e:
                logger.warning("Order poll failed: %s", e)

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return None

    async def submit_exit(
        self,
        position: EdgePosition,
        reason: str,
        current_price: float,
    ) -> str:
        """
        Submit exit order.

        V2: uses execution policy to choose NORMAL or PANIC_EXIT pricing
        V1 fallback: market sell
        """
        if self._has_v2:
            return await self._submit_exit_v2(position, reason, current_price)
        return await self._submit_exit_v1(position, reason, current_price)

    async def _submit_exit_v2(
        self,
        position: EdgePosition,
        reason: str,
        current_price: float,
    ) -> str:
        """V2 exit with execution quality layer."""
        assert self.quote_model is not None
        assert self.execution_policy is not None
        assert self.order_manager is not None

        try:
            quote = await self.quote_model.refresh(position.symbol)
            params = self.execution_policy.compute_exit_params(quote, reason)

            ticket = await self.order_manager.execute(
                symbol=position.symbol,
                side="sell",
                size_usd=position.size_usd,
                params=params,
                reference_mid=quote.mid,
            )

            fill_price = ticket.fill_price if ticket.fill_price else current_price
            pnl = position.compute_pnl(fill_price)

            status_map = {
                "take_profit": "closed_tp",
                "stop_loss": "closed_sl",
                "timeout": "closed_timeout",
                "regime_change": "closed_regime",
                "kill_switch": "closed_kill",
            }

            self.repo.update_position(position.position_id, {
                "status": status_map.get(reason, f"closed_{reason}"),
                "exit_price": fill_price,
                "exit_time": datetime.now(timezone.utc),
                "pnl_usd": pnl,
            })

            logger.info(
                "LIVE EXIT (V2): %s @ %.4f (reason=%s, pnl=$%.4f, mode=%s)",
                position.symbol, fill_price, reason, pnl, params.mode.value,
            )
            return ticket.order_id or position.position_id

        except Exception as e:
            logger.error("LIVE EXIT FAILED (V2): %s - %s", position.symbol, e)
            # Fall back to V1 exit on V2 failure
            return await self._submit_exit_v1(position, reason, current_price)

    async def _submit_exit_v1(
        self,
        position: EdgePosition,
        reason: str,
        current_price: float,
    ) -> str:
        """V1 exit: market sell."""
        client_order_id = f"ef-exit-{position.position_id[:8]}"

        try:
            qty = position.size_usd / position.entry_price if position.entry_price > 0 else 0

            order = await self.rh.place_order(
                symbol=position.symbol,
                side="sell",
                order_type="market",
                client_order_id=client_order_id,
                qty=qty,
            )

            order_id = order.get("id", client_order_id)
            fill_price = current_price
            pnl = position.compute_pnl(fill_price)

            status_map = {
                "take_profit": "closed_tp",
                "stop_loss": "closed_sl",
                "timeout": "closed_timeout",
                "regime_change": "closed_regime",
                "kill_switch": "closed_kill",
            }

            self.repo.update_position(position.position_id, {
                "status": status_map.get(reason, f"closed_{reason}"),
                "exit_price": fill_price,
                "exit_time": datetime.now(timezone.utc),
                "pnl_usd": pnl,
            })

            logger.info(
                "LIVE EXIT: %s @ ~%.4f (reason=%s, pnl=$%.4f, order=%s)",
                position.symbol, fill_price, reason, pnl, order_id,
            )
            return order_id

        except Exception as e:
            logger.error("LIVE EXIT FAILED: %s - %s", position.symbol, e)
            raise

    async def get_current_price(self, symbol: str) -> float:
        """Get mid price. V2 uses QuoteModel cache, V1 calls RH directly."""
        if self.quote_model is not None:
            mid = self.quote_model.mid_price(symbol)
            if mid > 0:
                return mid
            # Cache miss — refresh
            try:
                quote = await self.quote_model.refresh(symbol)
                return quote.mid
            except Exception:
                pass

        # V1 fallback
        try:
            data = await self.rh.get_best_bid_ask(symbol)
            results = data.get("results", [])
            if results:
                entry = results[0] if isinstance(results, list) else data
                bid = float(entry.get("bid_inclusive_of_sell_spread", entry.get("bid_price", 0)))
                ask = float(entry.get("ask_inclusive_of_buy_spread", entry.get("ask_price", 0)))
                return (bid + ask) / 2 if (bid + ask) > 0 else 0.0
        except Exception as e:
            logger.warning("Price fetch failed for %s: %s", symbol, e)
        return 0.0

    async def get_bid_price(self, symbol: str) -> float:
        """Get bid price. V2 uses QuoteModel cache, V1 calls RH directly."""
        if self.quote_model is not None:
            bid = self.quote_model.bid_price(symbol)
            if bid > 0:
                return bid
            try:
                quote = await self.quote_model.refresh(symbol)
                return quote.bid
            except Exception:
                pass

        # V1 fallback
        try:
            data = await self.rh.get_best_bid_ask(symbol)
            results = data.get("results", [])
            if results:
                entry = results[0] if isinstance(results, list) else data
                return float(entry.get("bid_inclusive_of_sell_spread", entry.get("bid_price", 0)))
        except Exception as e:
            logger.warning("Bid fetch failed for %s: %s", symbol, e)
        return 0.0
