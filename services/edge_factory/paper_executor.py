"""
High-fidelity paper executor for the Edge Factory.

Simulates realistic execution with:
  1. Latency simulation (200ms round-trip) — [HL] §Paper Mode
  2. BBO fills: buys at ask + slippage, sells at bid - slippage — [AA] §4.2
  3. Partial fill probability when spread is wide — [HL] §Paper Mode
  4. Order rejection on liquidity drought (spread > 1%) — [AA] §7.3

The goal is to make paper PnL WORSE than live PnL, so going live
is a positive surprise rather than a negative one.
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from .config import EdgeFactoryConfig
from .models import EdgePosition, Signal
from .repository import FeatureRepository

logger = logging.getLogger(__name__)


class PaperFillRejected(Exception):
    """Raised when paper fill is rejected due to market conditions."""
    pass


class PaperExecutor:
    """
    High-fidelity simulated execution for paper trading mode.

    Pessimistic fill model per Iron Lung research:
    - Buy fill: ask + slippage (worst case for buyer)
    - Sell fill: bid - slippage (worst case for seller)
    - 200ms latency simulation per order
    - Partial fill probability when spread is wide
    - Order rejection when spread > liquidity_threshold
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        repository: FeatureRepository,
    ):
        self.config = config
        self.repo = repository

        # Fill model parameters
        self.slippage_pct = 0.0005  # 0.05% slippage
        self.spread_pct = 0.003  # 0.3% default spread (conservative for RH)
        self.latency_ms = 200  # Simulated round-trip time (ms)

        # Partial fill parameters
        self.partial_fill_probability = 0.10  # 10% chance when spread is wide
        self.partial_fill_min_pct = 0.50  # Min fill: 50% of requested qty
        self.partial_fill_max_pct = 0.90  # Max fill: 90% of requested qty
        self.wide_spread_multiplier = 1.5  # Spread > 1.5x avg triggers partial fills

        # Liquidity rejection threshold
        self.liquidity_reject_spread_pct = 0.01  # 1% spread = reject order

        # Cached prices and BBO
        self._prices: dict[str, float] = {}  # symbol -> last/mid price
        self._bids: dict[str, float] = {}  # symbol -> best bid
        self._asks: dict[str, float] = {}  # symbol -> best ask
        self._avg_spread: float = self.spread_pct  # Rolling average spread

        # IS tracking (C3): set by orchestrator before each submit call
        self._decision_price: float = 0.0

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update cached prices from feature engine market data."""
        self._prices.update(prices)

    def update_bbo(self, symbol: str, bid: float, ask: float) -> None:
        """Update cached BBO for a symbol."""
        if bid > 0:
            self._bids[symbol] = bid
        if ask > 0:
            self._asks[symbol] = ask
        # Update rolling average spread
        if bid > 0 and ask > 0:
            spread = (ask - bid) / ((bid + ask) / 2)
            self._avg_spread = self._avg_spread * 0.95 + spread * 0.05

    def _get_bid(self, symbol: str) -> float:
        """Get best bid for symbol, computing from mid if not cached."""
        if symbol in self._bids and self._bids[symbol] > 0:
            return self._bids[symbol]
        price = self._prices.get(symbol, 0.0)
        return price * (1 - self.spread_pct / 2) if price > 0 else 0.0

    def _get_ask(self, symbol: str) -> float:
        """Get best ask for symbol, computing from mid if not cached."""
        if symbol in self._asks and self._asks[symbol] > 0:
            return self._asks[symbol]
        price = self._prices.get(symbol, 0.0)
        return price * (1 + self.spread_pct / 2) if price > 0 else 0.0

    def _current_spread_pct(self, symbol: str) -> float:
        """Compute current spread as a percentage."""
        bid = self._get_bid(symbol)
        ask = self._get_ask(symbol)
        if bid <= 0 or ask <= 0:
            return self.spread_pct
        mid = (bid + ask) / 2
        return (ask - bid) / mid if mid > 0 else self.spread_pct

    def _check_liquidity(self, symbol: str) -> None:
        """Reject order if spread indicates liquidity drought."""
        spread = self._current_spread_pct(symbol)
        if spread >= self.liquidity_reject_spread_pct:
            raise PaperFillRejected(
                f"Order rejected: {symbol} spread {spread:.2%} >= "
                f"liquidity threshold {self.liquidity_reject_spread_pct:.2%}"
            )

    def _apply_partial_fill(self, size_usd: float, symbol: str) -> float:
        """Possibly reduce fill size if spread is wide."""
        spread = self._current_spread_pct(symbol)
        if spread > self._avg_spread * self.wide_spread_multiplier:
            if random.random() < self.partial_fill_probability:
                fill_pct = random.uniform(
                    self.partial_fill_min_pct, self.partial_fill_max_pct
                )
                reduced = size_usd * fill_pct
                logger.info(
                    "PAPER PARTIAL FILL: %s reduced to %.0f%% ($%.2f → $%.2f) "
                    "due to wide spread (%.2f%%)",
                    symbol, fill_pct * 100, size_usd, reduced, spread * 100,
                )
                return reduced
        return size_usd

    def _emit_fill_quality(
        self,
        symbol: str,
        side: str,
        decision_price: float,
        fill_price: float,
        spread_at_decision_pct: float = 0.0,
    ) -> None:
        """
        Emit FILL_QUALITY event for implementation shortfall tracking (C3).

        IS = (fill_price - decision_price) / decision_price * 10000 bps
        References: [AA] §4.1, §4.3
        """
        if decision_price <= 0:
            return

        is_bps = ((fill_price - decision_price) / decision_price) * 10000.0

        # Record on metrics collector if available (stashed by runner.py)
        metrics = getattr(self, '_metrics', None)
        if metrics is not None:
            metrics.record_fill(
                symbol=symbol,
                side=side,
                decision_price=decision_price,
                fill_price=fill_price,
                spread_at_decision_pct=spread_at_decision_pct,
            )

        # Persist to local event store if available (stashed by runner.py)
        local_store = getattr(self, '_local_store', None)
        if local_store is not None:
            try:
                local_store.insert_event(
                    mode=self.config.mode,
                    source="edge_factory",
                    type="FILL_QUALITY",
                    subtype="IMPLEMENTATION_SHORTFALL",
                    symbol=symbol,
                    severity="info",
                    body=f"IS {is_bps:+.1f}bps {side} {symbol} "
                         f"decision={decision_price:.4f} fill={fill_price:.4f}",
                    meta={
                        "symbol": symbol,
                        "side": side,
                        "decision_price": decision_price,
                        "fill_price": fill_price,
                        "is_bps": round(is_bps, 2),
                        "spread_at_decision_pct": round(spread_at_decision_pct, 4),
                        "chase_steps": 0,
                    },
                )
            except Exception as e:
                logger.warning("Failed to persist FILL_QUALITY event: %s", e)

        logger.info(
            "FILL QUALITY: %s %s IS=%+.1f bps (decision=%.4f, fill=%.4f, spread=%.2f%%)",
            side.upper(), symbol, is_bps, decision_price, fill_price,
            spread_at_decision_pct * 100,
        )

    async def submit_entry(
        self,
        signal: Signal,
        size_usd: float,
        limit_price: float,
        tp_price: float,
        sl_price: float,
    ) -> str:
        """
        Simulate limit order entry with high-fidelity fill model.

        1. Check liquidity (reject if spread > 1%)
        2. Wait 200ms latency simulation
        3. Fill at ask + slippage (pessimistic for buyer)
        4. Apply partial fill probability if spread is wide
        """
        # 1. Liquidity check
        try:
            self._check_liquidity(signal.symbol)
        except PaperFillRejected as e:
            logger.warning("PAPER REJECT: %s", e)
            raise

        # 2. Latency simulation
        await asyncio.sleep(self.latency_ms / 1000.0)

        # 3. Pessimistic entry price: fill at ASK + slippage
        ask = self._get_ask(signal.symbol)
        if ask <= 0:
            ask = limit_price * (1 + self.spread_pct / 2)

        fill_price = ask + (ask * self.slippage_pct)

        # 4. Apply partial fill
        actual_size = self._apply_partial_fill(size_usd, signal.symbol)

        position_id = str(uuid.uuid4())
        position = EdgePosition(
            symbol=signal.symbol,
            side="buy",
            entry_price=fill_price,
            entry_time=datetime.now(timezone.utc),
            size_usd=actual_size,
            tp_price=tp_price,
            sl_price=sl_price,
            status="open",
            signal_id=signal.signal_id,
            order_id=f"paper-{position_id[:8]}",
            position_id=position_id,
        )

        self.repo.insert_position(position)

        logger.info(
            "PAPER ENTRY: %s $%.2f @ %.4f (ask=%.4f, slippage=%.4f) "
            "TP=%.4f SL=%.4f%s",
            signal.symbol, actual_size, fill_price, ask,
            ask * self.slippage_pct, tp_price, sl_price,
            f" [PARTIAL: ${size_usd:.2f}→${actual_size:.2f}]"
            if actual_size < size_usd else "",
        )

        # C3: Emit implementation shortfall
        decision = self._decision_price or self._prices.get(signal.symbol, 0.0)
        self._emit_fill_quality(
            symbol=signal.symbol,
            side="buy",
            decision_price=decision,
            fill_price=fill_price,
            spread_at_decision_pct=self._current_spread_pct(signal.symbol),
        )

        return position_id

    async def submit_exit(
        self,
        position: EdgePosition,
        reason: str,
        current_price: float,
    ) -> str:
        """
        Simulate exit with pessimistic fill model.

        1. Wait 200ms latency simulation
        2. Sell at BID - slippage (pessimistic for seller)
        """
        # Latency simulation
        await asyncio.sleep(self.latency_ms / 1000.0)

        # Pessimistic exit price: fill at BID - slippage
        bid = self._get_bid(position.symbol)
        if bid <= 0:
            bid = current_price * (1 - self.spread_pct / 2)

        fill_price = bid - (bid * self.slippage_pct)

        pnl = position.compute_pnl(fill_price)
        now = datetime.now(timezone.utc)

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
            "exit_time": now,
            "pnl_usd": pnl,
        })

        logger.info(
            "PAPER EXIT: %s @ %.4f (bid=%.4f, reason=%s, pnl=$%.4f)",
            position.symbol, fill_price, bid, reason, pnl,
        )

        # C3: Emit implementation shortfall for exit
        decision = self._decision_price or current_price
        self._emit_fill_quality(
            symbol=position.symbol,
            side="sell",
            decision_price=decision,
            fill_price=fill_price,
            spread_at_decision_pct=self._current_spread_pct(position.symbol),
        )

        return position.order_id or position.position_id

    async def get_current_price(self, symbol: str) -> float:
        """Get latest price from cached prices or feature store."""
        if symbol in self._prices and self._prices[symbol] > 0:
            return self._prices[symbol]
        # Fallback: check feature store metadata
        snap = self.repo.get_latest_feature(symbol, "vwap_distance")
        if snap and snap.metadata.get("current_price"):
            return snap.metadata["current_price"]
        return 0.0

    async def get_bid_price(self, symbol: str) -> float:
        """Get best bid price."""
        return self._get_bid(symbol)
