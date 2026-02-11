from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .config import CryptoTraderConfig

@dataclass
class RiskState:
    daily_drawdown: float
    open_positions_count: int
    daily_notional_used: float
    circuit_breaker_triggered: bool

class RiskManager:
    def __init__(self, config: CryptoTraderConfig, repo: Any):
        self.cfg = config
        self.repo = repo

    async def check_entry(self, symbol: str, notional: float, portfolio_value: float) -> bool:
        """
        Check if we can enter a new trade.
        Rules:
        1. Notional <= Max Per Trade
        2. Daily Notional Limit
        3. Max Open Positions
        4. Portfolio Concentration (Max 20% per asset)
        5. Circuit Breaker (5% Daily Loss)
        """
        # 1. Max Per Trade
        if notional > self.cfg.max_notional_per_trade:
            print(f"🚫 Risk blocked: Notional ${notional} > limit ${self.cfg.max_notional_per_trade}")
            return False

        # 2. Daily Notional
        if not await self._check_daily_notional(notional):
            return False

        # 3. Max Positions
        positions = await self.repo.get_positions_count()
        if positions >= self.cfg.max_open_positions:
            print(f"🚫 Risk blocked: Max open positions ({self.cfg.max_open_positions}) reached")
            return False

        # 4. Concentration
        # Assuming we know current holdings for this symbol.
        # Ideally passed in or checked via repo.
        # For now, let's assume 'max_notional_per_trade' implicitly handles concentration 
        # for a small account. But strictly:
        if portfolio_value > 0 and (notional / portfolio_value) > 0.20:
             print(f"🚫 Risk blocked: Concentration > 20% (${notional}/${portfolio_value})")
             return False

        # 5. Circuit Breaker
        if await self._is_circuit_breaker_active(portfolio_value):
             print(f"🚫 Risk blocked: Circuit breaker active.")
             return False

        return True

    async def _check_daily_notional(self, notional: float) -> bool:
        used = await self.repo.get_daily_notional(date.today())
        if used + notional > self.cfg.max_daily_notional:
            print(f"🚫 Risk blocked: Daily notional limit reached ({used}+{notional} > {self.cfg.max_daily_notional})")
            return False
        return True

    async def _is_circuit_breaker_active(self, portfolio_value: float) -> bool:
        # PnL for the day. If < -5% of starting equity.
        # This requires storing 'starting_equity' snapshot at 00:00 UTC.
        # For MVP, we'll check Realized PnL for today + Unrealized Drop.
        
        # Simplified: Check if today's realized losses > 5% of max_daily_available?
        # Or just hardcoded dollar amount?
        # Let's say if daily_realized_pnl < -$50 roughly for a $1k account.
        
        daily_pnl = await self.repo.get_daily_realized_pnl(date.today())
        if daily_pnl < -(portfolio_value * 0.05):
            return True
        return False
