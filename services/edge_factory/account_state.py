from __future__ import annotations

import logging
from typing import Any

from .config import EdgeFactoryConfig
from .repository import FeatureRepository

logger = logging.getLogger(__name__)


class AccountState:
    """
    Live equity tracker for the Edge Factory.

    In live mode: fetches RH get_account_balances() for real cash.
    In paper mode: uses static config value + realized PnL.
    Updates HWM (high water mark) if equity rises.
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        repository: FeatureRepository,
        rh_client: Any | None = None,
    ):
        self.config = config
        self.repo = repository
        self.rh = rh_client
        self._cached_equity: float = config.account_equity

    @property
    def equity(self) -> float:
        """Current equity (cached value)."""
        return self._cached_equity

    async def refresh(self) -> float:
        """Refresh equity from RH (live) or compute from PnL (paper)."""
        if self.config.is_live() and self.rh is not None:
            try:
                equity = await self._fetch_live_equity()
                self._cached_equity = equity
                self._update_hwm(equity)
                return equity
            except Exception as e:
                logger.warning("Live equity fetch failed: %s", e)
                return self._cached_equity

        # Paper mode: base equity + realized PnL
        equity = self._compute_paper_equity()
        self._cached_equity = equity
        self._update_hwm(equity)
        return equity

    async def _fetch_live_equity(self) -> float:
        """Fetch real equity from Robinhood."""
        data = await self.rh.get_account_balances()

        # RH returns various balance fields depending on account type
        if isinstance(data, dict):
            # Try crypto buying power first
            crypto_bp = data.get("crypto_buying_power")
            if crypto_bp is not None:
                return float(crypto_bp)

            # Try standard buying_power (RH crypto accounts return this)
            bp = data.get("buying_power")
            if bp is not None:
                return float(bp)

            # Fallback to portfolio value
            portfolio = data.get("equity", data.get("portfolio_value"))
            if portfolio is not None:
                return float(portfolio)

        return self.config.account_equity

    def _compute_paper_equity(self) -> float:
        """Compute paper equity from base + realized PnL."""
        base = self.config.account_equity
        closed = self.repo.get_closed_positions(limit=100)
        realized_pnl = sum(p.pnl_usd or 0 for p in closed)
        return base + realized_pnl

    def _update_hwm(self, equity: float) -> None:
        """Update high water mark if equity is new high."""
        current_hwm = self.repo.get_equity_high_water_mark()
        if equity > current_hwm:
            self.repo.set_equity_high_water_mark(equity)
            logger.info("New equity HWM: $%.2f (was $%.2f)", equity, current_hwm)

    def get_drawdown_from_hwm(self) -> float:
        """Current drawdown from HWM as a fraction (0.0 = at HWM, 0.1 = 10% below)."""
        hwm = self.repo.get_equity_high_water_mark()
        if hwm <= 0:
            return 0.0
        return max(0.0, (hwm - self._cached_equity) / hwm)

    def available_cash(self) -> float:
        """Cash not tied up in open positions."""
        open_positions = self.repo.get_open_positions()
        open_exposure = sum(p.size_usd for p in open_positions)
        return max(0.0, self._cached_equity - open_exposure)
