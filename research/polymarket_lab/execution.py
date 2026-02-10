import uuid
from .models import Trade, Market
from .accounting import AccountingEngine

class ExecutionEngine:
    def __init__(self, accounting: AccountingEngine):
        self.accounting = accounting

    def execute_paper_trade(self, market: Market, side: str, amount_usd: float) -> str:
        """Execute a simulated trade with slippage."""
        if not self.accounting.can_add_position(market.id, amount_usd, market.category):
            return "❌ Trade rejected: Risk limits exceeded or insufficient bankroll."

        # Model conservative slippage: 0.5% base + adjustment for liquidity
        # Base price is market_yes_price or (1-yes_price) for NO
        base_price = market.current_yes_price if side.upper() == "YES" else (1.0 - market.current_yes_price)
        
        # Slippage assumes wider spread for lower liquidity
        # Simple formula: 0.005 + (1000 / liquidity) * 0.01
        slippage_pct = 0.005 + (1000.0 / max(market.liquidity, 100)) * 0.01
        execution_price = base_price * (1.0 + slippage_pct)
        
        # Binary markets: price cannot exceed 0.99 for entry realistically
        execution_price = min(execution_price, 0.99)
        
        shares = amount_usd / execution_price
        
        trade = Trade(
            id=str(uuid.uuid4()),
            market_id=market.id,
            market_question=market.question,
            side=side.upper(),
            amount_usd=amount_usd,
            price_paid=execution_price,
            shares=shares,
            slippage_assumed=slippage_pct
        )
        
        self.accounting.record_trade(trade)
        
        return (f"✅ **Simulated Order Filled**\n"
                f"Market: {market.question}\n"
                f"Side: {side.upper()} | Amount: ${amount_usd:.2f}\n"
                f"Fill Price: {execution_price:.4f} (Est. Slippage: {slippage_pct*100:.2f}%)")
