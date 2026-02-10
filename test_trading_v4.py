"""
Test V4 Trading Engine (Paper Only)
"""
import time
import unittest
from trading_engine_v4 import TradingEngine, PaperBroker, RiskManager

class TestTradingV4(unittest.TestCase):
    def setUp(self):
        self.engine = TradingEngine()
        # Reset to default state
        self.engine.broker = PaperBroker() 
        self.engine.risk = RiskManager() 

    def test_initial_state(self):
        print("\n--- Testing Initial State ---")
        state = self.engine.broker.get_account_state()
        print(f"Equity: ${state['equity']}")
        self.assertEqual(state['equity'], 2000.0)
        self.assertEqual(state['pdt_count'], 0)

    def test_buy_fill(self):
        print("\n--- Testing Buy Order ---")
        # Buy 1 SPY Call @ $0.50 ($50 risk)
        res = self.engine.execute_trade("SPY_CALL_500", "buy", 1, 0.50)
        print(res)
        
        state = self.engine.broker.get_account_state()
        self.assertIn("SPY_CALL_500", state['positions'])
        self.assertEqual(state['positions']['SPY_CALL_500'], 1)
        self.assertEqual(state['cash'], 1950.0) # 2000 - 50

    def test_risk_rejection(self):
        print("\n--- Testing Risk Rejection ---")
        # Try to buy @ $2.00 ($200 cost) -> Should fail (Max risk $100)
        res = self.engine.execute_trade("SPY_CALL_500", "buy", 1, 2.00)
        print(res)
        self.assertIn("Rejected", res)

    def test_sell_position(self):
        print("\n--- Testing Sell (Close) ---")
        # Buy first
        self.engine.execute_trade("SPY_CALL_500", "buy", 1, 0.50)
        # Sell
        res = self.engine.execute_trade("SPY_CALL_500", "sell", 1, 0.60) # Profit
        print(res)
        
        state = self.engine.broker.get_account_state()
        self.assertNotIn("SPY_CALL_500", state['positions']) # Should be closed
        self.assertEqual(state['cash'], 2010.0) # 1950 + 60

if __name__ == '__main__':
    unittest.main()
