from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict

from integrations.robinhood_crypto_client import RobinhoodCryptoClient
from .config import CryptoTraderConfig

class Broker(ABC):
    @abstractmethod
    async def get_cash(self) -> float: ...
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, float]: ...
    
    @abstractmethod
    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]: ...

class RobinhoodBroker(Broker):
    def __init__(self, client: RobinhoodCryptoClient):
        self.client = client

    async def get_cash(self) -> float:
        balances = await self.client.get_account_balances()
        return float(balances.get("cash_available", 0.0))

    async def get_positions(self) -> Dict[str, float]:
        holdings_resp = await self.client.get_holdings()
        items = holdings_resp.get("results", [])
        return {
            item["symbol"]: float(item.get("quantity", 0.0)) 
            for item in items 
            if float(item.get("quantity", 0.0)) > 0
        }

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]:
        # Using Limit Orders by default as requested
        import uuid
        client_oid = f"zoe-prod-{uuid.uuid4()}"
        return await self.client.place_order(
            symbol=symbol,
            side=side,
            order_type="limit",
            client_order_id=client_oid,
            qty=qty,
            limit_price=limit_price
        )

class PaperBroker(Broker):
    """Simulates trades with pessimistic fills (Ask for Buy, Bid for Sell)."""
    def __init__(self, market_data_provider: Any, repo: Any):
        self.mdp = market_data_provider
        self.repo = repo
        self._cash = 2000.0 # Start with $2k paper
        self._positions: Dict[str, float] = {}

    async def get_cash(self) -> float:
        # In a real paper broker, we'd persist this to DB.
        # For now, reading from repo or memory.
        return self._cash

    async def get_positions(self) -> Dict[str, float]:
        return self._positions

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]:
        # Validate price against current market to simulate fill probability
        current_price = await self.mdp.get_current_price(symbol)
        
        # Slippage/Pessimism
        # If BUY: limit_price must be >= current_price * 1.001 (0.1% buffer) to fill immediately
        # If SELL: limit_price must be <= current_price * 0.999
        
        filled = False
        avg_price = 0.0
        
        if side == "buy":
            if limit_price >= current_price:
                filled = True
                avg_price = current_price * 1.001 # Slippage
        else: # sell
            if limit_price <= current_price:
                filled = True
                avg_price = current_price * 0.999 # Slippage
        
        import uuid
        order_id = str(uuid.uuid4())
        
        status = "filled" if filled else "open"
        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "type": "limit",
            "limit_price": limit_price,
            "status": status,
            "filled_qty": qty if filled else 0,
            "avg_price": avg_price,
        }
        
        if filled:
            # Update local state
            cost = qty * avg_price
            if side == "buy":
                if self._cash >= cost:
                    self._cash -= cost
                    self._positions[symbol] = self._positions.get(symbol, 0.0) + qty
                else:
                    order["status"] = "rejected"
                    order["reject_reason"] = "Insufficient funds"
            else:
                if self._positions.get(symbol, 0.0) >= qty:
                    self._cash += cost
                    self._positions[symbol] -= qty
                else:
                    order["status"] = "rejected"
                    order["reject_reason"] = "Insufficient position"

            # Log to DB
            await self.repo.insert_order(order)
            await self.repo.upsert_fill({
                "order_id": order_id,
                "fill_id": f"paper-fill-{uuid.uuid4()}",
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": avg_price,
                "executed_at": datetime.now(timezone.utc).isoformat()
            })
            
        return order
