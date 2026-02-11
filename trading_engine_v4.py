"""
Zoe V4 Trading Engine (Paper Only)
Implements the core loop, risk management, and delegates to real data sources.

V4.1 — Removed MockMarketData and internal PaperBroker.
        Now uses Polygon (market_data) for prices and Supabase (paper_broker) for orders.
"""
import time
import logging
import yaml
from datetime import datetime
from typing import Dict, Optional, Any

from market_data import market_data
from paper_broker import paper_broker

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ZoeTradingEngine")

# Load config for trading limits
try:
    with open("config.yaml", "r") as f:
        _TRADING_CFG = yaml.safe_load(f).get("trading", {})
except Exception:
    _TRADING_CFG = {}


class RiskManager:
    """Enforces V4 Risk Rules (Hard Limits)."""

    def __init__(
        self,
        max_risk_per_trade: float = None,
        max_day_trades: int = None,
    ):
        self.max_risk = max_risk_per_trade or _TRADING_CFG.get("max_risk_per_trade", 100.0)
        self.max_pdt = max_day_trades or _TRADING_CFG.get("pdt_max_day_trades", 3)

    def check_order(self, order_cost: float, is_day_trade: bool = False) -> bool:
        """Returns True if order is allowed, False otherwise."""
        # 1. Risk Per Trade
        if order_cost > self.max_risk:
            logger.warning(f"🚫 Risk Reject: Order cost {order_cost} > Max Risk {self.max_risk}")
            return False

        # 2. PDT Check (simplified — full check in paper_broker)
        # Future: query paper_broker for day-trade count
        return True


class TradingEngine:
    """
    Main loop controller. Delegates to real singletons:
      - market_data (Polygon) for prices
      - paper_broker (Supabase) for order execution
    """

    def __init__(self):
        self.risk = RiskManager()
        self.is_running = False
        self.paper_only = _TRADING_CFG.get("paper_only", True)
        self._starting_equity = _TRADING_CFG.get("starting_equity", 2000)

    def start(self):
        self.is_running = True
        mode = "Paper" if self.paper_only else "LIVE"
        logger.info(f"🚀 Zoe Trading Engine Started ({mode} Mode)")

    def stop(self):
        self.is_running = False
        logger.info("🛑 Zoe Trading Engine Stopped")

    def run_tick(self):
        """One iteration of the trading loop (called every minute by scheduler)."""
        if not self.is_running:
            return
        # Crypto candle analysis is handled by the crypto_candle_loop in clawdbot.py
        # Options scanning is triggered by /scan slash command
        # This method is available for future scheduled equity scans
        pass

    def execute_trade(self, symbol: str, side: str, quantity: int, price: float, discord_id: str = "292890243852664855") -> str:
        """Manual/Bot entry point for trades."""
        # Risk Check
        cost = price * quantity * 100 if side == "buy" else 0

        if side == "buy" and not self.risk.check_order(cost):
            return "❌ Order Rejected by Risk Manager."

        # Execute via paper_broker (Supabase-backed)
        import asyncio

        order = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "limit_price": price,
            "strategy": "V4_MANUAL",
        }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context — schedule as task
                asyncio.create_task(paper_broker.place_order(order, discord_id))
            else:
                loop.run_until_complete(paper_broker.place_order(order, discord_id))
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return f"❌ Trade failed: {e}"

        # Trigger Engagement
        try:
            from clawdbot import engagement_engine

            if engagement_engine:
                event_type = "TRADE_OPEN" if side == "buy" else "TRADE_CLOSE_GREEN"
                asyncio.create_task(
                    engagement_engine.post_trade_event(
                        event_type=event_type,
                        trade_id=f"ord_{int(time.time()*1000)}",
                        symbol=symbol,
                        details={
                            "side": side,
                            "qty": quantity,
                            "price": price,
                            "strategy": "V4_MANUAL",
                        },
                    )
                )
        except Exception as e:
            logger.warning(f"⚠️ Engagement trigger failed: {e}")

        return f"✅ Order Submitted: {side} {quantity} {symbol} @ {price}"

    def get_status(self) -> str:
        """Return human-readable status using real data sources."""
        try:
            # Use paper_broker for account summary (Supabase-backed)
            summary = paper_broker.get_account_summary("292890243852664855")
            equity = summary.get("equity", self._starting_equity)
            pnl = summary.get("pnl", 0)
            count = summary.get("open_count", 0)
            mode = "Paper" if self.paper_only else "LIVE"
            return f"{mode} Acct: Equity=${equity:,.2f} | PnL=${pnl:,.2f} | Pos={count}"
        except Exception:
            return f"Paper Acct: Equity=${self._starting_equity:,.2f} | Status=Initializing"


# Global Instance
engine = TradingEngine()
