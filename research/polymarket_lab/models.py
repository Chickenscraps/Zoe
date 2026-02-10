from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Market:
    id: str
    question: str
    slug: str
    current_yes_price: float
    volume: float
    liquidity: float
    end_date_iso: Optional[str] = None
    category: Optional[str] = None

@dataclass
class Trade:
    id: str
    market_id: str
    market_question: str
    side: str  # 'YES' or 'NO'
    amount_usd: float
    price_paid: float
    shares: float
    timestamp: datetime = field(default_factory=datetime.now)
    slippage_assumed: float = 0.0

@dataclass
class Position:
    market_id: str
    market_question: str
    side: str
    shares: float
    avg_entry_price: float
    current_price: float
    
    @property
    def cost_basis(self) -> float:
        return self.shares * self.avg_entry_price
    
    @property
    def current_value(self) -> float:
        return self.shares * self.current_price
    
    @property
    def unrealized_pnl_usd(self) -> float:
        return self.current_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl_usd / self.cost_basis) * 100
