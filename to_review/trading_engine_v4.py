"""
Zoe V4 Trading Engine (Paper Only)
Implements the core loop, risk management, and simulated broker.
"""
import time
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ZoeTradingEngine")

class MockMarketData:
    """Mock Provider until Polygon is connected."""
    def get_price(self, symbol: str) -> float:
        # Mock jitter around a base price
        base = 100.0  # Default
        if symbol == 'SPY': base = 500.0
        elif symbol == 'QQQ': base = 400.0
        elif symbol == 'IWM': base = 200.0
        return base + (random.random() - 0.5) * 2.0

class RiskManager:
    """Enforces V4 Risk Rules (Hard Limits)."""
    def __init__(self, max_risk_per_trade: float = 100.0, max_day_trades: int = 3):
        self.max_risk = max_risk_per_trade
        self.max_pdt = max_day_trades

    def check_order(self, account_state: Dict, order_cost: float, is_day_trade: bool = False) -> bool:
        """
        Returns True if order is allowed, False otherwise.
        """
        # 1. Capital Check
        if account_state['buying_power'] < order_cost:
            logger.warning(f"🚫 Risk Reject: Insufficient BP ({account_state['buying_power']} < {order_cost})")
            return False
            
        # 2. Risk Per Trade
        if order_cost > self.max_risk:
            logger.warning(f"🚫 Risk Reject: Order cost {order_cost} > Max Risk {self.max_risk}")
            return False
            
        # 3. PDT Check
        if is_day_trade:
            if account_state['pdt_count'] >= self.max_pdt:
                logger.warning(f"🚫 Risk Reject: PDT Limit Reached ({account_state['pdt_count']}/{self.max_pdt})")
                return False

        return True

class PaperBroker:
    """Simulates a broker (Fills, Position Tracking)."""
    def __init__(self, starting_equity: float = 2000.0):
        self.account = {
            "equity": starting_equity,
            "cash": starting_equity,
            "buying_power": starting_equity,
            "pdt_count": 0,
            "positions": {} # symbol -> quantity
        }
        self.fills = []
        
        # persistence
        try:
            from supabase_memory import supabase_memory
            self.db = supabase_memory.client
        except:
            self.db = None
            logger.warning("⚠️ Persistence disabled: Supabase client not found.")

    def _persist(self, table: str, data: Dict):
        """Helper to write to Supabase safely."""
        if not self.db: return
        try:
            self.db.table(table).insert(data).execute()
        except Exception as e:
            logger.error(f"❌ DB Write Failed ({table}): {e}")

    def submit_order(self, symbol: str, quantity: int, side: str, price: float) -> Dict:
        """Execute a paper order immediately (Market/Limit treated as fillable)."""
        cost = price * quantity * 100 # Standard option multiplier
        timestamp = datetime.now().isoformat()
        
        # 1. Create Order Object
        order_id = f"ord_{int(time.time()*1000)}"
        order = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "type": "limit",
            "status": "filled", # Instant fill
            "created_at": timestamp,
            "filled_at": timestamp,
            "legs": [{"symbol": symbol, "side": side, "ratio": 1}]
        }
        
        # DB: Write Order
        # Note: In real app we'd map this to the 'orders' table schema exactly
        # For now we skip strict schema mapping to avoid breakage if keys mismatch
        
        # 2. Update Account Memory
        if side == 'buy':
            self.account['cash'] -= cost
            self.account['buying_power'] -= cost
            current_qty = self.account['positions'].get(symbol, 0)
            self.account['positions'][symbol] = current_qty + quantity
            
        elif side == 'sell':
            self.account['cash'] += cost
            self.account['buying_power'] += cost
            current_qty = self.account['positions'].get(symbol, 0)
            self.account['positions'][symbol] = current_qty - quantity
            
            if self.account['positions'][symbol] == 0:
                del self.account['positions'][symbol]
                
        # 3. Create Fill Record
        fill = {
            "id": f"fill_{int(time.time()*1000)}",
            "order_id": order_id, # Link (mock)
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "timestamp": timestamp
        }
        self.fills.append(fill)
        
        # 4. DB Persistence (Best Effort)
        if self.db:
            try:
                # We need a user_id to link to accounts. 
                # For V4 Paper Mode, we'll fetch the first user or use a dummy ID if needed.
                # Ideally this is passed in.
                pass 
                # self.db.table("fills").insert(fill).execute()
                # self.db.table("orders").insert(order).execute()
                # self.db.table("positions").upsert(...).execute()
            except Exception as e:
                logger.error(f"DB Error: {e}")

        logger.info(f"✅ Paper Fill: {side.upper()} {quantity} {symbol} @ ${price:.2f}")
        return fill

    def get_account_state(self) -> Dict:
        return self.account

class TradingEngine:
    """Main Loop Controller."""
    def __init__(self):
        self.broker = PaperBroker()
        self.risk = RiskManager()
        self.market = MockMarketData()
        self.is_running = False

    def start(self):
        self.is_running = True
        logger.info("🚀 Zoe Trading Engine Started (Paper Mode)")

    def stop(self):
        self.is_running = False
        logger.info("🛑 Zoe Trading Engine Stopped")

    def run_tick(self):
        """One iteration of the trading loop (e.g. called every minute)."""
        if not self.is_running: return
        
        # 1. Market Data Tick
        spy_price = self.market.get_price('SPY')
        # logger.info(f"Tick: SPY=${spy_price:.2f}")
        
        # 2. Strategy Scan (Mock)
        # Here we would call the Strategy modules
        pass

    def execute_trade(self, symbol: str, side: str, quantity: int, price: float) -> str:
        """Manual/Bot entry point for trades."""
        # Risk Check
        cost = price * quantity * 100 if side == 'buy' else 0
        state = self.broker.get_account_state()
        
        if side == 'buy' and not self.risk.check_order(state, cost, is_day_trade=False):
            return "❌ Order Rejected by Risk Manager."
            
        # Execute
        fill = self.broker.submit_order(symbol, quantity, side, price)
        
        # Trigger Engagement
        try:
            from clawdbot import engagement_engine
            if engagement_engine:
                import asyncio
                event_type = "TRADE_OPEN" if side == 'buy' else "TRADE_CLOSE_GREEN"
                # If side is sell, try to determine if it was green or red
                # (Simple logic: if sell price > avg entry price)
                # For now, simplistic mapping
                
                asyncio.create_task(engagement_engine.post_trade_event(
                    event_type=event_type,
                    trade_id=fill['id'],
                    symbol=symbol,
                    details={
                        "side": side,
                        "qty": quantity,
                        "price": price,
                        "strategy": "V4_AUTOMATED"
                    }
                ))
        except Exception as e:
            logger.warning(f"⚠️ Engagement trigger failed: {e}")

        return f"✅ Order Filled: {side} {quantity} {symbol} @ {price}"

    def close_position(self, symbol: str, quantity: int, price: float) -> str:
        """Explicitly close a position and report P&L."""
        state = self.broker.get_account_state()
        if symbol not in state['positions']:
            return f"❌ No open position in {symbol}"

        # Execute Sell
        fill = self.broker.submit_order(symbol, quantity, 'sell', price)
        
        # Trigger Engagement with GREEN/RED logic
        try:
            from clawdbot import engagement_engine
            if engagement_engine:
                import asyncio
                # Mock P&L check
                pnl = random.uniform(-500, 1000) 
                event_type = "TRADE_CLOSE_GREEN" if pnl > 0 else "TRADE_CLOSE_RED"
                
                asyncio.create_task(engagement_engine.post_trade_event(
                    event_type=event_type,
                    trade_id=fill['id'],
                    symbol=symbol,
                    details={
                        "side": "sell",
                        "qty": quantity,
                        "price": price,
                        "pnl": f"${pnl:.2f}",
                        "strategy": "V4_AUTOMATED"
                    }
                ))
        except Exception as e:
            logger.warning(f"⚠️ Engagement trigger failed: {e}")

        return f"✅ Position Closed: {symbol} @ {price}"

    def get_status(self) -> str:
        state = self.broker.get_account_state()
        return f"Paper Acct: Equity=${state['equity']:.2f} | BP=${state['buying_power']:.2f} | Pos={len(state['positions'])}"

# Global Instance
engine = TradingEngine()
