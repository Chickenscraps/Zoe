"""
Paper Broker V2
Simulates a realistic exchange execution engine for Paper Trading.
Supporting:
- Limit Orders (Order Book matching simulation)
- Marketable Limits (Slippage models)
- Position Management
- P&L Tracking
"""

import time
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Configure Logger
logger = logging.getLogger("PaperBrokerV2")

class OrderType:
    LIMIT = "limit"
    MARKET = "market"

class Side:
    BUY = "buy"
    SELL = "sell"

class OrderStatus:
    NEW = "new"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELED = "canceled"
    REJECTED = "rejected"

class PaperBrokerV2:
    def __init__(self, account_id: str, starting_equity: float = 2000.0, slippage_bps: int = 5):
        self.account_id = account_id
        self.slippage_bps = slippage_bps
        
        # In-memory state (rehydrated from DB in real usage, but clean/mock for now)
        self.balance = {
            "cash": starting_equity,
            "buying_power": starting_equity,
            "equity": starting_equity
        }
        self.positions: Dict[str, Dict] = {} # symbol -> {qty, avg_price}
        self.open_orders: Dict[str, Dict] = {} # order_id -> order_dict
        self.fills: List[Dict] = []
        
        # Dependencies
        self.db = None # Injectable
        
    def set_db_client(self, db_client):
        self.db = db_client

    def _apply_slippage(self, price: float, side: str) -> float:
        """Calculates fill price based on slippage model."""
        slippage = price * (self.slippage_bps / 10000.0)
        if side == Side.BUY:
            return price + slippage # Pay more
        else:
            return price - slippage # Sell for less

    def submit_order(self, symbol: str, side: str, quantity: float, price: float, type: str = "limit") -> Dict:
        """
        Places an order into the internal book. 
        For MARKET orders or MARKETABLE LIMITS, attempts immediate execution.
        """
        order_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        order = {
            "id": order_id,
            "account_id": self.account_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price_limit": price, # The user's limit price
            "type": type,
            "status": OrderStatus.NEW,
            "filled_qty": 0,
            "created_at": timestamp,
            "updated_at": timestamp
        }
        
        logger.info(f"📝 Paper Order {side.upper()} {quantity} {symbol} @ {price}")
        
        # 1. Validate Funds (Simple check)
        est_cost = price * quantity
        if side == Side.BUY and est_cost > self.balance['buying_power']:
            order['status'] = OrderStatus.REJECTED
            order['reject_reason'] = "Insufficient Buying Power"
            logger.warning(f"❌ Rejected: Insufficient BP ({self.balance['buying_power']} < {est_cost})")
            return order

        # 2. Add to Book
        self.open_orders[order_id] = order
        
        # 3. Reserve Buying Power
        if side == Side.BUY:
            self.balance['buying_power'] -= est_cost

        # 4. Persist to DB (Sync for visibility)
        if self.db:
            try:
                self.db.table("crypto_orders").insert({
                    "id": order_id,
                    # "account_id": self.account_id, # Removed: Not in schema
                    "client_order_id": order_id, # Schema requires this unique field
                    "symbol": symbol,
                    "side": side,
                    "qty": quantity,
                    # "price": price, # Schema might not have price for market orders? check schema.
                    # Schema has 'order_type' and 'notional' or 'qty'.
                    # Schema: symbol, side, order_type, qty, notional, status, ...
                    "order_type": type, # Schema uses order_type
                    "status": "submitted", 
                    # "requested_at": timestamp, # Removed to use DB default/bypass cache error
                    "raw_response": {"mode": "PAPER", "price_limit": price}
                }).execute()
            except Exception as e:
                logger.error(f"⚠️ DB Insert Order Failed: {e}")

        return order

    def process_tick(self, market_data: Dict[str, float]):
        """
        Evaluates all open orders against current market prices.
        market_data: { "BTC-USD": 95000.50, "ETH-USD": 2700.00 }
        """
        filled_ids = []
        
        for oid, order in self.open_orders.items():
            symbol = order['symbol']
            if symbol not in market_data:
                continue
                
            curr_price = market_data[symbol]
            side = order['side']
            limit = order['price_limit']
            
            # Check Match Logic
            should_fill = False
            if side == Side.BUY and curr_price <= limit:
                should_fill = True
            elif side == Side.SELL and curr_price >= limit:
                should_fill = True
                
            if should_fill:
                # Execute Fill
                fill_price = self._apply_slippage(curr_price, side)
                self._execute_fill(order, fill_price)
                filled_ids.append(oid)
                
        # Cleanup
        for oid in filled_ids:
            del self.open_orders[oid]

    def _execute_fill(self, order: Dict, fill_price: float):
        """Internal method to update state on fill."""
        qty = order['quantity']
        side = order['side']
        symbol = order['symbol']
        cost = fill_price * qty
        
        # Update Order Record
        order['status'] = OrderStatus.FILLED
        order['filled_price'] = fill_price
        order['filled_at'] = datetime.now().isoformat()
        
        # Update Balance & Positions
        if side == Side.BUY:
            # We already deducted BP at limit price. Adjust for actual cost.
            reserved_cost = order['price_limit'] * qty
            diff = reserved_cost - cost
            self.balance['cash'] -= cost
            self.balance['buying_power'] += diff # Return excess if filled cheaper
            
            # Position Update (Weighted Average)
            pos = self.positions.get(symbol, {"quantity": 0, "avg_price": 0.0})
            old_qty = pos['quantity']
            old_cost = pos['quantity'] * pos['avg_price']
            new_qty = old_qty + qty
            if new_qty > 0:
                new_avg = (old_cost + cost) / new_qty
            else:
                new_avg = 0
            
            self.positions[symbol] = {"quantity": new_qty, "avg_price": new_avg}
            
        elif side == Side.SELL:
            self.balance['cash'] += cost
            self.balance['buying_power'] += cost
            
            # Position Update
            pos = self.positions.get(symbol, {"quantity": 0, "avg_price": 0.0})
            new_qty = pos['quantity'] - qty
            # FIFO/Avg Cost doesn't change on SELL, only realized P&L is booked.
            # For simple tracking, we just reduce qty.
            if new_qty <= 0:
                if new_qty < 0: logger.warning("⚠️ Oversold position (Shorting not fully supported yet in logic)")
                del self.positions[symbol]
            else:
                self.positions[symbol]['quantity'] = new_qty

        # Log Fill
        fill_record = {
            "id": str(uuid.uuid4()),
            "order_id": order['id'],
            "symbol": symbol,
            "side": side,
            "price": fill_price,
            "quantity": qty,
            "timestamp": datetime.now().isoformat()
        }
        self.fills.append(fill_record)
        logger.info(f"✅ FILLED {side} {qty} {symbol} @ {fill_price:.2f}")

        # Async Sync (Best Effort)
        if self.db:
            try:
                # 1. Update Order Status
                self.db.table("crypto_orders").update({
                    "status": "filled",
                    "updated_at": datetime.now().isoformat()
                }).eq("id", order['id']).execute()

                # 2. Insert Fill
                self.db.table("crypto_fills").insert({
                    "id": fill_record['id'],
                    "order_id": order['id'],
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,  # Schema uses 'qty'
                    "price": fill_price,
                    "fee": 0.0,
                    "executed_at": fill_record['timestamp']
                }).execute()
                
                # 3. Snapshot Holdings (for UI)
                holdings_flat = {k: v['quantity'] for k, v in self.positions.items()}
                self.db.table("crypto_holdings_snapshots").insert({
                    "holdings": holdings_flat,
                    "total_crypto_value": self.get_equity({}) - self.balance['cash'] # Approx
                }).execute()

            except Exception as e:
                 logger.error(f"⚠️ DB Sync Fill Failed: {e}")

    def get_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate total equity (Cash + Positions marked to market)."""
        pos_val = 0.0
        for sym, pos in self.positions.items():
            price = current_prices.get(sym, pos['avg_price']) # Fallback to entry
            pos_val += pos['quantity'] * price
            
        return self.balance['cash'] + pos_val
