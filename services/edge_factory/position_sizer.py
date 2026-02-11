from __future__ import annotations

import logging
import math

from .config import EdgeFactoryConfig
from .models import RegimeState, Signal
from .repository import FeatureRepository

logger = logging.getLogger(__name__)


class PositionSizer:
    """
    Half-Kelly position sizing for crypto trades.

    Full Kelly: f* = (p * b - q) / b
    where p = win_rate, b = avg_win/avg_loss, q = 1-p

    We use Half-Kelly (f*/2) and cap at config.max_position_pct.

    For V1 with limited history, conservative defaults:
    - win_rate = 0.45 (pessimistic)
    - reward_risk = 2.0 (TP 4% / SL 2%)
    """

    DEFAULT_WIN_RATE = 0.45
    DEFAULT_REWARD_RISK = 2.0
    MIN_TRADE_SIZE = 1.0  # Minimum $1 trade

    def __init__(self, config: EdgeFactoryConfig, repository: FeatureRepository):
        self.config = config
        self.repo = repository

    def compute_size(
        self,
        signal: Signal,
        current_price: float,
        account_equity: float | None = None,
    ) -> tuple[float, float, float]:
        """
        Compute position size, take-profit price, and stop-loss price.

        Returns (size_usd, tp_price, sl_price).
        """
        equity = account_equity or self.config.account_equity

        # Compute Kelly fraction
        kelly = self._estimate_kelly()

        # Base size from Kelly
        kelly_size = equity * kelly

        # Apply regime multiplier
        regime_mult = signal.regime.sizing_multiplier()
        regime_adjusted = kelly_size * regime_mult

        # Apply signal strength scaling (stronger signal = closer to max)
        strength_adjusted = regime_adjusted * (0.5 + 0.5 * signal.strength)

        # Apply volatility adjustment if available
        vol_adj = signal.features.get("volatility_adjusted_size")
        if vol_adj is not None and vol_adj > 0:
            strength_adjusted = min(strength_adjusted, vol_adj)

        # Enforce caps
        max_size = self.config.max_position_usd()
        final_size = max(
            min(strength_adjusted, max_size),
            self.MIN_TRADE_SIZE,
        )

        # Round to cents
        final_size = round(final_size, 2)

        # Compute TP and SL prices
        tp_price = round(current_price * (1 + self.config.take_profit_pct), 8)
        sl_price = round(current_price * (1 - self.config.stop_loss_pct), 8)

        logger.info(
            "SIZE %s: $%.2f (kelly=%.3f, regime=%.1f, strength=%.2f) "
            "TP=%.2f SL=%.2f",
            signal.symbol, final_size, kelly, regime_mult,
            signal.strength, tp_price, sl_price,
        )

        return final_size, tp_price, sl_price

    def _estimate_kelly(self) -> float:
        """
        Estimate Kelly fraction from trade history.
        Falls back to conservative defaults if < 20 closed trades.

        Full Kelly: f* = (p * b - q) / b
        Half Kelly: f*/2
        """
        closed = self.repo.get_closed_positions(limit=50)
        if len(closed) < 20:
            # Not enough history — use defaults
            p = self.DEFAULT_WIN_RATE
            b = self.DEFAULT_REWARD_RISK
        else:
            wins = [pos for pos in closed if (pos.pnl_usd or 0) > 0]
            losses = [pos for pos in closed if (pos.pnl_usd or 0) <= 0]

            p = len(wins) / len(closed) if closed else self.DEFAULT_WIN_RATE

            avg_win = (
                sum(pos.pnl_usd or 0 for pos in wins) / len(wins)
                if wins else self.config.take_profit_pct
            )
            avg_loss = (
                abs(sum(pos.pnl_usd or 0 for pos in losses) / len(losses))
                if losses else self.config.stop_loss_pct
            )
            b = avg_win / avg_loss if avg_loss > 0 else self.DEFAULT_REWARD_RISK

        q = 1 - p
        full_kelly = (p * b - q) / b if b > 0 else 0
        half_kelly = full_kelly * self.config.kelly_fraction

        # Clamp: never bet more than max_position_pct, never negative
        clamped = max(min(half_kelly, self.config.max_position_pct), 0.01)

        return clamped
