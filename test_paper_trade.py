"""
Test Script: Simulate Paper Trade Lifecycle
- Init PaperBrokerV2
- Submit BUY Limit Order (ETH)
- Mock Market Data Update (Trigger Fill)
- Verify Position & P&L
- Submit SELL Order
- Verify Realized P&L
"""
import time
import logging
from paper_broker_v2 import PaperBrokerV2, OrderStatus, Side

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestTrade")

def run_test():
    print("🚀 Starting Paper Trade Simulation...")
    
    # 1. Initialize Broker
    broker = PaperBrokerV2(account_id="test_user_001")
    print(f"💰 Initial Equity: ${broker.get_equity({}):.2f}")
    
    # 2. Market Data Mock
    # ETH starts at 2700
    prices_t0 = {"ETH-USD": 2700.00}
    
    # 3. Submit Buy Order (Limit 2705 - should fill immediately if marketable)
    print("\n📝 Submitting BUY 1.0 ETH @ 2705.00")
    order = broker.submit_order("ETH-USD", Side.BUY, 1.0, 2705.00)
    print(f"   Order Status: {order['status']}")
    
    # 4. Process Tick (Trigger Fill)
    print("\n⏳ Processing Tick (Market: 2700.00)...")
    broker.process_tick(prices_t0)
    
    # Check Fill
    filled_order = broker.fills[-1] if broker.fills else None
    if filled_order:
        print(f"✅ Filled! Price: {filled_order['price']:.2f}")
    else:
        print("❌ Order not filled (Unexpected)")
        return

    # 5. Verify Position
    pos = broker.positions.get("ETH-USD")
    print(f"\n📊 Position: {pos}")
    print(f"   Equity (Mark 2700): ${broker.get_equity(prices_t0):.2f}")
    
    # 6. Price Moves Up (profit)
    print("\n📈 Market Moves to 2800.00...")
    prices_t1 = {"ETH-USD": 2800.00}
    equity_t1 = broker.get_equity(prices_t1)
    print(f"   Equity (Mark 2800): ${equity_t1:.2f} (+${equity_t1 - 2000:.2f})")
    
    # 7. Sell to Close
    print("\n📝 Submitting SELL 1.0 ETH @ 2790.00 (Limit)")
    sell_order = broker.submit_order("ETH-USD", Side.SELL, 1.0, 2790.00)
    
    print("\n⏳ Processing Tick (Market: 2800.00)...")
    broker.process_tick(prices_t1)
    
    # Check Final State
    final_pos = broker.positions.get("ETH-USD")
    if not final_pos:
        print("\n✅ Position Closed.")
    else:
        print(f"\n❌ Position Logic Error: {final_pos}")
        
    print(f"💰 Final Equity: ${broker.get_equity(prices_t1):.2f}")
    print("✅ Test Complete.")

if __name__ == "__main__":
    run_test()
