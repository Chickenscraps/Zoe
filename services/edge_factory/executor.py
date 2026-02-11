from __future__ import annotations

from typing import Protocol

from .models import EdgePosition, Signal


class EdgeFactoryExecutor(Protocol):
    """Interface for execution backends (paper or live)."""

    async def submit_entry(
        self,
        signal: Signal,
        size_usd: float,
        limit_price: float,
        tp_price: float,
        sl_price: float,
    ) -> str:
        """Submit entry order. Returns position_id."""
        ...

    async def submit_exit(
        self,
        position: EdgePosition,
        reason: str,
        current_price: float,
    ) -> str:
        """Submit exit order. Returns order_id."""
        ...

    async def get_current_price(self, symbol: str) -> float:
        """Get current mid price for a symbol."""
        ...

    async def get_bid_price(self, symbol: str) -> float:
        """Get current bid price (for limit buy entries)."""
        ...
