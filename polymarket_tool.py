
"""
Polymarket Paper Trader (Real Lab Bridge)
Bridges the Discord bot to the research research/polymarket_lab infrastructure.
"""
import uuid
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List

from research.polymarket_lab.api_client import PolymarketClient
from research.polymarket_lab.accounting import AccountingEngine
from research.polymarket_lab.execution import ExecutionEngine
from research.polymarket_lab.models import Market

class PolymarketTrader:
    def __init__(self):
        self.logger = logging.getLogger("polymarket")
        self.api = PolymarketClient()
        self.accounting = AccountingEngine()
        self.execution = ExecutionEngine(self.accounting)

    async def search_markets(self, query: str) -> str:
        """Search real available markets."""
        markets = await self.api.fetch_active_markets(limit=20)
        query = query.lower()
        results = []
        for m in markets:
            if query in m.question.lower() or query in m.slug.lower():
                results.append(f"- **{m.id}**: {m.question} (Yes: {int(m.current_yes_price*100)}%)")
        
        if not results:
            return f"🤷 No real markets found matching '{query}'."
        return "\n".join(results)

    async def place_trade(self, profile_id: str, market_id: str, side: str, amount: float) -> str:
        """Place a paper trade using the real execution engine."""
        # Note: profile_id is used for ledger tracking in accounting
        # We need to fetch the market object first
        response = await self.api.client.get(f"{self.api.GAMMA_BASE_URL}/markets/{market_id}")
        if response.status_code != 200:
            return f"❌ Market {market_id} not found on Polymarket."
        
        data = response.json()
        market = Market(
            id=data["id"],
            question=data["question"],
            slug=data["slug"],
            current_yes_price=float(data.get("last_trade_price", 0.5)),
            volume=float(data.get("volume", 0)),
            liquidity=float(data.get("liquidity", 0))
        )
        
        result = self.execution.execute_paper_trade(market, side, amount)
        return result

    async def get_portfolio(self, profile_id: str) -> str:
        """Get user portfolio from the real accounting ledger."""
        if not self.accounting.positions:
            return "📉 Your paper portfolio is empty."
            
        lines = [f"💼 **Real-Data Paper Portfolio** (Equity: ${self.accounting.total_equity:.2f})"]
        for market_id, pos in self.accounting.positions.items():
            lines.append(f"- {pos.side.upper()} on {pos.market_question}: {pos.shares:.2f} shares (PnL: ${pos.unrealized_pnl_usd:+.2f})")
            
        return "\n".join(lines)

    async def handle_tool_call(self, args: Dict[str, Any]) -> str:
        """Handler for LLM tool calls."""
        action = args.get("action")
        if action == "search":
            return await self.search_markets(args.get("query", ""))
        elif action == "trade":
            return await self.place_trade("bot_user", args.get("market_id"), args.get("side"), args.get("amount", 10.0))
        elif action == "portfolio":
            return await self.get_portfolio("bot_user")
        return "Unknown action."
