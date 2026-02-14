from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List

from .config import CryptoTraderConfig


class Broker(ABC):
    @abstractmethod
    async def get_cash(self) -> float: ...

    @abstractmethod
    async def get_positions(self) -> Dict[str, float]: ...

    @abstractmethod
    async def get_total_usd(self) -> float: ...

    @abstractmethod
    async def get_open_orders(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]: ...

    async def close(self) -> None:
        """Clean up resources."""
        pass


class KrakenBroker(Broker):
    """Live broker backed by Kraken REST API."""

    def __init__(self, client: Any, usd_converter: Any):
        from integrations.kraken_client import KrakenClient, USDConverter
        self.client: KrakenClient = client
        self.usd: USDConverter = usd_converter

    async def get_cash(self) -> float:
        """Return total fiat (USD + USDT converted to USD)."""
        balances = await self.client.get_normalized_balances()
        total_cash = 0.0
        for asset in ("USD", "USDT", "USDC", "DAI"):
            qty = balances.get(asset, 0.0)
            if qty > 0:
                price = await self.usd.get_usd_price(asset)
                total_cash += qty * price
        return total_cash

    async def get_positions(self) -> Dict[str, float]:
        """Return non-fiat holdings as {symbol-USD: qty}.

        Normalizes to BTC-USD format matching our DB convention.
        """
        balances = await self.client.get_normalized_balances()
        fiat = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "KRW", "USDT", "USDC", "DAI"}
        positions: Dict[str, float] = {}
        for asset, qty in balances.items():
            if asset in fiat or qty <= 0:
                continue
            symbol = f"{asset}-USD"
            positions[symbol] = qty
        return positions

    async def get_total_usd(self) -> float:
        """Total portfolio value in USD (all assets)."""
        balances = await self.client.get_normalized_balances()
        return await self.usd.total_usd(balances)

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """Return open orders in normalized format."""
        return await self.client.get_normalized_open_orders()

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]:
        from integrations.kraken_client.client import denormalize_pair
        pair = denormalize_pair(symbol)
        result = await self.client.place_order(
            pair=pair,
            side=side,
            ordertype="limit",
            volume=qty,
            price=limit_price,
        )
        txid = result.get("txid", [""])[0] if isinstance(result.get("txid"), list) else str(result.get("txid", ""))
        return {
            "id": txid,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "limit_price": limit_price,
            "status": "submitted",
            "raw": result,
        }

    async def get_ticker_prices(self, symbols: list[str]) -> Dict[str, float]:
        """Fetch mid-prices for a list of symbols (BTC-USD format).

        Returns {symbol: mid_price}.
        """
        from integrations.kraken_client.client import denormalize_pair
        pairs = [denormalize_pair(s) for s in symbols]
        tickers = await self.client.get_ticker(pairs)
        result: Dict[str, float] = {}
        for i, symbol in enumerate(symbols):
            kraken_pair = pairs[i]
            # Kraken may return with different key
            for key, data in tickers.items():
                if kraken_pair in key or key in kraken_pair:
                    bid = float(data["b"][0])
                    ask = float(data["a"][0])
                    result[symbol] = (bid + ask) / 2.0
                    break
        return result

    async def close(self) -> None:
        await self.client.close()


class RobinhoodBroker(Broker):
    def __init__(self, client: Any):
        from integrations.robinhood_crypto_client import RobinhoodCryptoClient
        self.client: RobinhoodCryptoClient = client

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

    async def get_total_usd(self) -> float:
        # Robinhood doesn't have a single total; approximate from cash + positions value
        cash = await self.get_cash()
        return cash  # Positions market value would require price fetches

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        return []  # Robinhood order polling handled differently

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]:
        client_oid = f"zoe-prod-{uuid.uuid4()}"
        return await self.client.place_order(
            symbol=symbol,
            side=side,
            order_type="limit",
            client_order_id=client_oid,
            qty=qty,
            limit_price=limit_price
        )

    async def close(self) -> None:
        await self.client.close()


class PaperBroker(Broker):
    """Simulates trades with pessimistic fills (Ask for Buy, Bid for Sell)."""
    def __init__(self, market_data_provider: Any, repo: Any):
        self.mdp = market_data_provider
        self.repo = repo
        self._cash = 2000.0
        self._positions: Dict[str, float] = {}

    async def get_cash(self) -> float:
        return self._cash

    async def get_positions(self) -> Dict[str, float]:
        return self._positions

    async def get_total_usd(self) -> float:
        return self._cash  # Paper mode doesn't track market value

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        return []

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]:
        current_price = await self.mdp.get_current_price(symbol)
        filled = False
        avg_price = 0.0

        if side == "buy":
            if limit_price >= current_price:
                filled = True
                avg_price = current_price * 1.001
        else:
            if limit_price <= current_price:
                filled = True
                avg_price = current_price * 0.999

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

            self.repo.insert_order(order)
            self.repo.upsert_fill({
                "order_id": order_id,
                "fill_id": f"paper-fill-{uuid.uuid4()}",
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": avg_price,
                "executed_at": datetime.now(timezone.utc).isoformat()
            })

        return order

    async def close(self) -> None:
        pass
