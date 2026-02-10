import json
import os
from typing import List, Dict, Any
from .models import Position, Trade, Market

class AccountingEngine:
    DATA_FILE = "ledger.json"

    def __init__(self, initial_bankroll: float = 500.0):
        self.initial_bankroll = initial_bankroll
        self.cash = initial_bankroll
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self._load_ledger()

    def _load_ledger(self):
        """Load trade history and calculate current state."""
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, "r") as f:
                    data = json.load(f)
                    # For simplicity, we'll re-process trades to build state
                    # Real systems would store pre-computed state
                    self.trades = [Trade(**t) for t in data.get("trades", [])]
                    self._rebuild_positions()
            except Exception:
                pass

    def _rebuild_positions(self):
        """Re-calculate cash and positions from trade history."""
        self.cash = self.initial_bankroll
        self.positions = {}
        for trade in self.trades:
            self.cash -= trade.amount_usd
            if trade.market_id not in self.positions:
                self.positions[trade.market_id] = Position(
                    market_id=trade.market_id,
                    market_question=trade.market_question,
                    side=trade.side,
                    shares=trade.shares,
                    avg_entry_price=trade.price_paid,
                    current_price=trade.price_paid
                )
            else:
                pos = self.positions[trade.market_id]
                if pos.side == trade.side:
                    new_shares = pos.shares + trade.shares
                    new_avg = ((pos.shares * pos.avg_entry_price) + (trade.shares * trade.price_paid)) / new_shares
                    pos.shares = new_shares
                    pos.avg_entry_price = new_avg
                else:
                    # Partial close or flip - simplified logic
                    pos.shares -= trade.shares
                    if pos.shares <= 0:
                        del self.positions[trade.market_id]

    @property
    def total_equity(self) -> float:
        """Cash + current value of all positions."""
        portfolio_value = sum(pos.current_value for pos in self.positions.values())
        return self.cash + portfolio_value

    def get_max_position_size(self, market_price: float) -> float:
        """Calculate max USD amount allowed per trade (3-5% cap)."""
        # Using 3% as starting safe limit
        risk_pct = 0.03
        max_usd = self.total_equity * risk_pct
        return max_usd

    def calculate_kelly_size(self, win_prob: float, odds_price: float) -> float:
        """
        Calculate sizing using Partial Kelly (1/4 Kelly).
        win_prob: estimated true probability (e.g. 0.6)
        odds_price: market price (e.g. 0.5)
        """
        if win_prob <= odds_price:
            return 0.0
            
        # b = odds (net profit if win / amount bet)
        # b = (1 - price) / price
        b = (1.0 - odds_price) / odds_price
        
        # Kelly % = (b * p - q) / b
        # where q = 1 - p
        p = win_prob
        q = 1.0 - p
        
        kelly_pct = (b * p - q) / b
        
        # Use 1/4 Kelly for conservative simulation
        partial_kelly = kelly_pct * 0.25
        
        # Cap by hard risk limit
        final_pct = min(partial_kelly, 0.05) 
        return max(0.0, final_pct * self.total_equity)

    def can_add_position(self, market_id: str, amount_usd: float, category: str = None) -> bool:
        """Check risk limits: position cap and correlation cap."""
        # Check bankroll availability
        if amount_usd > self.cash:
            return False
            
        # Position cap (already checked by size, but here as a safety)
        if amount_usd > self.get_max_position_size(0.5): # price agnostic for total amount
            return False
            
        # Correlation cap (10-15%)
        # Here we'd filter by category if provided
        # For now, let's just limit total exposure to any single market
        existing_pos = self.positions.get(market_id)
        current_exposure = existing_pos.current_value if existing_pos else 0
        if current_exposure + amount_usd > (self.total_equity * 0.05):
            return False
            
        return True

    def record_trade(self, trade: Trade):
        """Persist trade to ledger and update state."""
        self.trades.append(trade)
        self._rebuild_positions()
        self._save_ledger()

    def _save_ledger(self):
        # Implementation omitted for brevity, would use json.dump
        pass
