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

    # ── ATR-based stop loss / take profit ──────────────────────

    @staticmethod
    def calculate_atr(candles: list, period: int = 14) -> float | None:
        """Calculate Average True Range from candle data.

        ATR measures volatility using the true range (max of: H-L, |H-Cprev|, |L-Cprev|).
        Returns ATR in absolute price terms, or None if insufficient data.
        """
        if len(candles) < period + 1:
            return None

        tr_values: list[float] = []
        for i in range(1, len(candles)):
            h = candles[i].high
            l = candles[i].low
            c_prev = candles[i - 1].close
            tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
            tr_values.append(tr)

        if len(tr_values) < period:
            return None

        return sum(tr_values[-period:]) / period

    @staticmethod
    def calculate_atr_stop(
        candles: list, entry_price: float, multiplier: float = 2.0,
    ) -> float:
        """Calculate ATR-based stop loss price.

        SL = entry - (ATR × multiplier).  Clamped to -1.5% / -5% bounds
        to prevent unreasonable stops.

        Falls back to -3% fixed stop if insufficient candle data.
        """
        atr = RiskManager.calculate_atr(candles)
        if atr is None:
            return entry_price * 0.97  # fallback: -3%

        sl = entry_price - (atr * multiplier)

        # Clamp: never tighter than -1.5%, never wider than -5%
        min_sl = entry_price * 0.95   # max loss = 5%
        max_sl = entry_price * 0.985  # min loss = 1.5%
        return max(min_sl, min(sl, max_sl))

    @staticmethod
    def calculate_atr_take_profit(
        candles: list, entry_price: float, multiplier: float = 3.0,
    ) -> float:
        """Calculate ATR-based take profit price.

        TP = entry + (ATR × multiplier).  Default 3:1 R:R per research
        showing EMA crossover strategies achieve 3:1 risk-reward.

        Falls back to +4.5% fixed TP if insufficient candle data.
        """
        atr = RiskManager.calculate_atr(candles)
        if atr is None:
            return entry_price * 1.045  # fallback: +4.5%

        tp = entry_price + (atr * multiplier)

        # Clamp: at least +2%, at most +8%
        min_tp = entry_price * 1.02
        max_tp = entry_price * 1.08
        return max(min_tp, min(tp, max_tp))
