"""Unified exchange client protocol for broker-agnostic trading.

KrakenClient satisfies this protocol, providing a unified interface
for the trading engines.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class ExchangeClient(Protocol):
    """Protocol defining the exchange client interface used by trading engines."""

    async def get_account_balances(self) -> dict[str, Any]:
        """Get all asset balances."""
        ...

    async def get_holdings(self) -> dict[str, Any]:
        """Get non-fiat holdings with quantities."""
        ...

    async def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        client_order_id: str,
        qty: Optional[float] = None,
        notional: Optional[float] = None,
        limit_price: Optional[float] = None,
    ) -> dict[str, Any]:
        """Place an order. Returns dict with at least 'id' and 'status'."""
        ...

    async def get_order(self, order_id: str) -> dict[str, Any]:
        """Query order status. Returns dict with 'id', 'status', etc."""
        ...

    async def get_order_fills(self, order_id: str) -> dict[str, Any]:
        """Get fills for an order. Returns {'results': [...]}."""
        ...

    async def get_best_bid_ask(self, symbol: str) -> dict[str, Any]:
        """Get current bid/ask for a symbol.

        Returns: {'results': [{'bid_price': str, 'ask_price': str, ...}]}
        """
        ...

    async def get_best_bid_ask_batch(self, symbols: list[str]) -> dict[str, Any]:
        """Get current bid/ask for multiple symbols in one call."""
        ...

    async def get_trading_pairs(
        self, symbols: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """Get available trading pairs."""
        ...

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open order."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
