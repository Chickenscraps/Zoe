import json
import os
import random
import time
from datetime import datetime, timedelta
from .polymarket_lab.accounting import AccountingEngine

# Path to UI public folder
UI_PUBLIC_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui-clawdbot", "public")

class DashboardGenerator:
    def __init__(self):
        self.accounting = AccountingEngine()

    def generate_signals(self):
        """Generate mock signals for X and Google Trends (until real APIs are hooked up)."""
        # In a real scenario, this would read from a database or API cache
        trending_topics = ["Bitcoin", "Election", "AI Regulation", "SpaceX", "Interest Rates"]
        
        signals = []
        for _ in range(3):
            topic = random.choice(trending_topics)
            sentiment = random.choice(["Bullish", "Bearish", "Neutral"])
            source = random.choice(["X (Twitter)", "Google Trends", "Polymarket Volume"])
            signals.append({
                "id": str(random.randint(1000, 9999)),
                "timestamp": datetime.now().isoformat(),
                "topic": topic,
                "sentiment": sentiment,
                "source": source,
                "confidence": random.uniform(0.6, 0.95),
                "summary": f"High velocity detected in {topic} discussions. Sentiment leaning {sentiment}."
            })
        return signals

    def get_dashboard_data(self):
        """Aggregate all data for the dashboard."""
        
        # Portfolio Data
        portfolio = {
            "total_equity": self.accounting.total_equity,
            "cash": self.accounting.cash,
            "pnl_24h": random.uniform(-50, 150), # Mocked for now, needs historical tracking
            "win_rate": 0.65, # Mocked
            "positions": []
        }

        for market_id, pos in self.accounting.positions.items():
            portfolio["positions"].append({
                "market_id": market_id,
                "question": pos.market_question,
                "side": pos.side,
                "shares": pos.shares,
                "avg_price": pos.avg_price,
                "current_value": pos.shares * 0.5, # Mock current price if not live
                "pnl": pos.unrealized_pnl_usd
            })

        # Recent Trades (Last 5)
        recent_trades = [t.__dict__ for t in self.accounting.trade_history[-5:]] if self.accounting.trade_history else []

        data = {
            "last_updated": datetime.now().isoformat(),
            "status": "ONLINE",
            "portfolio": portfolio,
            "signals": self.generate_signals(),
            "recent_trades": recent_trades
        }
        return data

    def update_file(self):
        """Write data to the UI public folder."""
        data = self.get_dashboard_data()
        
        if not os.path.exists(UI_PUBLIC_PATH):
            os.makedirs(UI_PUBLIC_PATH, exist_ok=True)
            
        file_path = os.path.join(UI_PUBLIC_PATH, "dashboard_data.json")
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        return file_path
