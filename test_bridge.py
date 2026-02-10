import asyncio
import sys
import os

# Ensure we can import the modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from polymarket_tool import PolymarketTrader

async def test_bot_bridge():
    trader = PolymarketTrader()
    print("🔍 Testing Real-Data Search (Query: 'Trump')...")
    results = await trader.search_markets("Trump")
    print(results)
    
    print("\n💼 Checking Portfolio (Initial)...")
    portfolio = await trader.get_portfolio("test_user")
    print(portfolio)

if __name__ == "__main__":
    asyncio.run(test_bot_bridge())
