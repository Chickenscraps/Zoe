from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from .config import EdgeFactoryConfig
from .models import EdgePosition, Signal
from .repository import FeatureRepository

logger = logging.getLogger(__name__)


class PaperExecutor:
    """
    Simulated execution for paper trading mode.

    Pessimistic fill model (from Edge Factory design doc):
    - Buy fill: price + spread + slippage (worst case)
    - Sell fill: price - spread - slippage (worst case)

    This intentionally overestimates costs so paper->live divergence
    is in the user's favor.
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        repository: FeatureRepository,
    ):
        self.config = config
        self.repo = repository
        self.slippage_pct = 0.0005  # 0.05% slippage
        self.spread_pct = 0.003  # 0.3% default spread (conservative for RH)
        self._prices: dict[str, float] = {}  # symbol -> latest price

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update cached prices from feature engine market data."""
        self._prices.update(prices)

    async def submit_entry(
        self,
        signal: Signal,
        size_usd: float,
        limit_price: float,
        tp_price: float,
        sl_price: float,
    ) -> str:
        """
        Simulate limit order entry with pessimistic fill.

        In paper mode, we assume the order fills immediately at a
        pessimistically adjusted price (limit + spread + slippage).
        """
        # Pessimistic entry price
        friction = limit_price * (self.spread_pct + self.slippage_pct)
        fill_price = limit_price + friction

        position_id = str(uuid.uuid4())
        position = EdgePosition(
            symbol=signal.symbol,
            side="buy",
            entry_price=fill_price,
            entry_time=datetime.now(timezone.utc),
            size_usd=size_usd,
            tp_price=tp_price,
            sl_price=sl_price,
            status="open",
            signal_id=signal.signal_id,
            order_id=f"paper-{position_id[:8]}",
            position_id=position_id,
        )

        self.repo.insert_position(position)

        logger.info(
            "PAPER ENTRY: %s $%.2f @ %.4f (limit=%.4f, friction=%.4f) "
            "TP=%.4f SL=%.4f",
            signal.symbol, size_usd, fill_price, limit_price,
            friction, tp_price, sl_price,
        )

        return position_id

    async def submit_exit(
        self,
        position: EdgePosition,
        reason: str,
        current_price: float,
    ) -> str:
        """
        Simulate exit with pessimistic fill.
        Sell fills at price - spread - slippage.
        """
        friction = current_price * (self.spread_pct + self.slippage_pct)
        fill_price = current_price - friction

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
            "PAPER EXIT: %s @ %.4f (reason=%s, pnl=$%.4f)",
            position.symbol, fill_price, reason, pnl,
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
        """For paper mode, bid = current_price - half spread."""
        price = await self.get_current_price(symbol)
        return price * (1 - self.spread_pct / 2)
