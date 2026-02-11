from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import EdgeFactoryConfig
from .models import EdgePosition, Signal
from .position_sizer import PositionSizer
from .repository import FeatureRepository

logger = logging.getLogger(__name__)


@dataclass
class TradeIntent:
    """Structured intent between signal generation and execution."""

    symbol: str
    direction: str  # "long"
    size_usd: float
    limit_price: float
    tp_price: float
    sl_price: float
    expected_move_pct: float
    signal_strength: float
    regime: str
    churn_cleared: bool = True
    block_reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TradeIntentBuilder:
    """
    Sits between SignalGenerator and Executor.

    Takes a Signal + features + current price, runs sizing and churn gates,
    returns a TradeIntent ready for execution (or None if blocked).
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        sizer: PositionSizer,
        repository: FeatureRepository,
    ):
        self.config = config
        self.sizer = sizer
        self.repo = repository

    def build(
        self,
        signal: Signal,
        features: dict[str, float],
        current_price: float,
        account_equity: float | None = None,
    ) -> TradeIntent | None:
        """
        Build a TradeIntent from a signal.

        Returns None if blocked by any churn gate, with reason logged.
        """
        equity = account_equity or self.config.account_equity

        # Get expected move (required for churn control)
        expected_move = features.get("expected_move_pct")
        if expected_move is None or expected_move <= 0:
            logger.info(
                "INTENT BLOCKED %s: no expected_move_pct available",
                signal.symbol,
            )
            return None

        # Run churn control gates
        block_reason = self._check_churn_gates(
            signal.symbol, expected_move, equity, features
        )
        if block_reason:
            logger.info(
                "INTENT BLOCKED %s: %s", signal.symbol, block_reason
            )
            return None

        # Size the position
        size_usd, tp_price, sl_price = self.sizer.compute_size(
            signal, current_price, equity
        )

        # Min trade notional check
        if size_usd < self.config.min_trade_notional:
            logger.info(
                "INTENT BLOCKED %s: size $%.2f < min $%.2f",
                signal.symbol, size_usd, self.config.min_trade_notional,
            )
            return None

        return TradeIntent(
            symbol=signal.symbol,
            direction=signal.direction,
            size_usd=size_usd,
            limit_price=current_price,
            tp_price=tp_price,
            sl_price=sl_price,
            expected_move_pct=expected_move,
            signal_strength=signal.strength,
            regime=signal.regime.regime,
            churn_cleared=True,
        )

    def _check_churn_gates(
        self,
        symbol: str,
        expected_move: float,
        equity: float,
        features: dict[str, float],
    ) -> str:
        """
        Run all churn control gates.
        Returns empty string if all pass, or reason string if blocked.
        """
        # Gate 1: Per-symbol cooldown
        reason = self._check_cooldown(symbol)
        if reason:
            return reason

        # Gate 2: Min expected move (don't enter if can't reach TP)
        if expected_move < self.config.min_expected_move_pct:
            return (
                "expected_move %.2f%% < min %.2f%%"
                % (expected_move * 100, self.config.min_expected_move_pct * 100)
            )

        # Gate 3: Daily turnover cap
        reason = self._check_turnover(equity)
        if reason:
            return reason

        # Gate 4: Concentration (no duplicate symbol)
        reason = self._check_concentration(symbol)
        if reason:
            return reason

        # Gate 5: Min remaining equity
        open_positions = self.repo.get_open_positions()
        open_exposure = sum(p.size_usd for p in open_positions)
        remaining = equity - open_exposure
        if remaining < self.config.min_remaining_equity:
            return "remaining equity $%.2f < min $%.2f" % (
                remaining, self.config.min_remaining_equity,
            )

        return ""

    def _check_cooldown(self, symbol: str) -> str:
        """Block if same symbol traded < cooldown_hours ago."""
        from datetime import timedelta

        cooldown = timedelta(hours=self.config.symbol_cooldown_hours)
        now = datetime.now(timezone.utc)

        # Check recent closed positions for this symbol
        closed = self.repo.get_closed_positions(limit=50)
        for pos in closed:
            if pos.symbol != symbol:
                continue
            exit_time = pos.exit_time or pos.entry_time
            if (now - exit_time) < cooldown:
                hours_ago = (now - exit_time).total_seconds() / 3600
                return "cooldown: %s traded %.1fh ago (min %dh)" % (
                    symbol, hours_ago, self.config.symbol_cooldown_hours,
                )

        return ""

    def _check_turnover(self, equity: float) -> str:
        """Block if daily notional exceeds turnover cap."""
        from datetime import date

        today = date.today()
        daily_used = self.repo.get_daily_notional(today)
        cap = equity * self.config.daily_turnover_cap_mult

        if daily_used >= cap:
            return "daily turnover $%.2f >= cap $%.2f (%.1fx equity)" % (
                daily_used, cap, self.config.daily_turnover_cap_mult,
            )

        return ""

    def _check_concentration(self, symbol: str) -> str:
        """Block if symbol already has an open position."""
        open_positions = self.repo.get_open_positions()
        for pos in open_positions:
            if pos.symbol == symbol:
                return "concentration: %s already has open position" % symbol

        return ""
