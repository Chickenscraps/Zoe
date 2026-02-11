from __future__ import annotations

from typing import Any

from ..models import FeatureSnapshot
from .base import BaseFeature


class PortfolioHeat(BaseFeature):
    """
    Current active exposure as a percentage of total account equity.

    heat = sum(open_position_sizes_usd) / account_equity

    Signal: heat < 60% means room for new positions.
    """

    name = "portfolio_heat"
    source = "computed"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        open_exposure = raw_data.get("open_exposure_usd", 0.0)
        account_equity = raw_data.get("account_equity", 150.0)
        if account_equity <= 0:
            return 1.0  # Fully loaded / no equity
        return open_exposure / account_equity


class DrawdownCurrent(BaseFeature):
    """
    Current drawdown from the equity high water mark.

    drawdown = (hwm - current_equity) / hwm

    Signal: drawdown > 20% triggers kill switch.
    """

    name = "drawdown_current"
    source = "computed"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        hwm = raw_data.get("equity_hwm", 150.0)
        current = raw_data.get("account_equity", 150.0)
        if hwm <= 0:
            return 0.0
        dd = (hwm - current) / hwm
        return max(dd, 0.0)


class ConsecutiveLossCount(BaseFeature):
    """
    Number of consecutive losing trades.

    Used for anti-martingale sizing: reduce size during losing streaks.
    Signal: count >= 4 blocks new entries (tilt protection).
    """

    name = "consecutive_loss_count"
    source = "computed"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        count = raw_data.get("consecutive_losses", 0)
        return float(count)


class VolatilityAdjustedSize(BaseFeature):
    """
    Recommended position size adjusted for current volatility.

    size = (risk_per_trade / (volatility * stop_distance)) * equity

    Where risk_per_trade = kelly_fraction * max_position_pct
    """

    name = "volatility_adjusted_size"
    source = "computed"

    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        vol = raw_data.get("garman_klass_vol", 0.5)  # Annualized vol
        equity = raw_data.get("account_equity", 150.0)
        max_pct = raw_data.get("max_position_pct", 0.15)
        sl_pct = raw_data.get("stop_loss_pct", 0.02)

        if vol <= 0 or sl_pct <= 0:
            return equity * max_pct

        # Daily vol from annual
        daily_vol = vol / (365 ** 0.5)

        # Risk budget: how much we're willing to lose
        risk_budget = equity * max_pct * sl_pct

        # Position size = risk_budget / (daily_vol * price_risk_factor)
        vol_factor = max(daily_vol * 2, sl_pct)  # At least SL distance
        size = risk_budget / vol_factor

        # Cap at max position
        return min(size, equity * max_pct)
