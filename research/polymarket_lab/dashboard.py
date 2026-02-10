from .accounting import AccountingEngine
from .models import Position

class Dashboard:
    def __init__(self, accounting: AccountingEngine):
        self.accounting = accounting

    def render_cli(self):
        """Render a text-based dashboard to the console."""
        print("\n" + "="*50)
        print("📊 POLYMARKET PAPERTRADING LAB DASHBOARD")
        print("="*50)
        
        # Summary
        equity = self.accounting.total_equity
        profit = equity - self.accounting.initial_bankroll
        profit_pct = (profit / self.accounting.initial_bankroll) * 100
        
        print(f"Equity:     ${equity:,.2f}")
        print(f"Cash:       ${self.accounting.cash:,.2f}")
        print(f"PnL:        ${profit:+,.2f} ({profit_pct:+.2f}%)")
        print("-" * 50)
        
        # Positions
        print("OPEN POSITIONS:")
        if not self.accounting.positions:
            print("  None")
        for market_id, pos in self.accounting.positions.items():
            print(f"- {pos.market_question}")
            print(f"  Side: {pos.side} | Shares: {pos.shares:.2f} | Entry: {pos.avg_entry_price:.4f} | PnL: ${pos.unrealized_pnl_usd:+.2f} ({pos.unrealized_pnl_pct:+.2f}%)")
        
        print("-" * 50)
        # Risk Metrics
        exposure_pct = ((equity - self.accounting.cash) / equity) * 100
        print(f"Total Exposure: {exposure_pct:.1f}%")
        print("="*50 + "\n")

    def generate_markdown_report(self) -> str:
        """Generate a markdown report for sharing."""
        # Implementation for automated walkthrough generation
        pass
