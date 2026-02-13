from __future__ import annotations

import logging
from typing import Any

from .config import EdgeFactoryConfig
from .repository import FeatureRepository

logger = logging.getLogger(__name__)


class AccountState:
    """
    Live equity tracker for the Edge Factory.

    In live mode: fetches exchange balances for cash, plus mark-to-market
    crypto positions from market_snapshot_focus for total equity.
    In paper mode: uses static config value + realized PnL.
    Updates HWM (high water mark) if equity rises.
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        repository: FeatureRepository,
        exchange_client: Any | None = None,
        supabase_client: Any | None = None,
    ):
        self.config = config
        self.repo = repository
        self.exchange = exchange_client
        self._sb = supabase_client
        self._cached_equity: float = config.account_equity
        self._cached_cash: float = 0.0
        self._cached_crypto_value: float = 0.0

    @property
    def equity(self) -> float:
        """Current total equity (cash + crypto MTM, cached)."""
        return self._cached_equity

    @property
    def cash_usd(self) -> float:
        """Current USD cash balance (cached)."""
        return self._cached_cash

    @property
    def crypto_value(self) -> float:
        """Current crypto holdings value at mark (cached)."""
        return self._cached_crypto_value

    async def refresh(self) -> float:
        """Refresh equity from exchange (live) or compute from PnL (paper)."""
        if self.config.is_live() and self.exchange is not None:
            try:
                cash = await self._fetch_live_cash()
                crypto_val = await self._fetch_crypto_mark_value()
                equity = cash + crypto_val
                self._cached_cash = cash
                self._cached_crypto_value = crypto_val
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

    async def _fetch_live_cash(self) -> float:
        """Fetch USD cash balance from exchange."""
        data = await self.exchange.get_account_balances()

        if isinstance(data, dict):
            # Kraken returns {"ZUSD": "123.45", "XXBT": "0.5", ...}
            for key in ("ZUSD", "USD", "USDT"):
                if key in data:
                    val = float(data[key])
                    if val > 0:
                        return val

            # RH compatibility: try crypto buying power, buying_power
            crypto_bp = data.get("crypto_buying_power")
            if crypto_bp is not None:
                return float(crypto_bp)

            bp = data.get("buying_power")
            if bp is not None:
                return float(bp)

            portfolio = data.get("equity", data.get("portfolio_value"))
            if portfolio is not None:
                return float(portfolio)

        return self.config.account_equity

    async def _fetch_crypto_mark_value(self) -> float:
        """Compute total crypto holdings value using mark prices from focus snapshots."""
        if not self._sb or not self.exchange:
            return 0.0

        try:
            # Get current holdings from exchange
            holdings_data = await self.exchange.get_holdings()
            holdings = holdings_data if isinstance(holdings_data, dict) else {}
            if not holdings:
                return 0.0

            # Get mark prices from focus snapshots
            symbols = list(holdings.keys())
            resp = self._sb.table("market_snapshot_focus").select(
                "symbol, mid"
            ).in_("symbol", symbols).execute()
            marks = {r["symbol"]: float(r["mid"]) for r in (resp.data or []) if float(r.get("mid", 0)) > 0}

            total = 0.0
            for sym, qty in holdings.items():
                mark = marks.get(sym, 0.0)
                if mark > 0:
                    total += float(qty) * mark
            return total
        except Exception as e:
            logger.debug("Crypto mark value fetch failed: %s", e)
            return 0.0

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
