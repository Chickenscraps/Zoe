
import os
import sys
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Setup paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from game_server_manager import GameServerManager
from polymarket_tool import PolymarketTrader
from tool_maps import read_url

async def test_game_manager():
    print("\n🧪 Testing Game Server Manager...")
    
    # Mock gate
    mock_gate = MagicMock()
    mock_gate.check_permission = AsyncMock(return_value=True)
    
    manager = GameServerManager(mock_gate)
    
    # List
    lst = await manager.list_servers()
    print(f"   List output: {lst[:50]}...")
    assert "minecraft" in lst
    
    # Start
    res = await manager.start_server("minecraft", 123)
    print(f"   Start output: {res}")
    assert "started" in res
    
    # Verify gate called
    mock_gate.check_permission.assert_called_with("start_server", 123, "Start minecraft")

async def test_polymarket():
    print("\n🧪 Testing Polymarket Trader...")
    trader = PolymarketTrader()
    
    # Search
    res = await trader.search_markets("trump")
    print(f"   Search result: {res}")
    assert "trump" in res.lower()
    
    # Buy
    res = await trader.place_trade("test_user", "trump_win", "yes", 50.0)
    print(f"   Trade result: {res}")
    assert "Trade Executed" in res
    
    # Portfolio
    port = await trader.get_portfolio("test_user")
    port = await trader.get_portfolio("test_user")
    print(f"   Portfolio: {port}")
    assert "Trump wins" in port

def test_browser_tools():
    print("\n🧪 Testing Browser Tools...")
    # Mock requests.get
    # Since read_url makes extensive network calls, we might skip full network test or mock it.
    # For now, let's just ensure the function exists and handles a mock url if we could mock requests.
    # We will rely on the fact that if it imports, it's good, and test failure mode.
    
    res = read_url("bad_url")
    print(f"   Bad URL result: {res[:50]}...")
    assert "Error" in res or "Schema" in res

if __name__ == "__main__":
    asyncio.run(test_game_manager())
    asyncio.run(test_polymarket())
    test_browser_tools()
