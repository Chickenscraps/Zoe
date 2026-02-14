"""P&L computation service.

Computes:
  - Per-position unrealized P&L: (mid_price - avg_cost) * qty
  - Portfolio realized P&L: sum of all closed trades' gains/losses
  - Cumulative fees from fee_ledger
  - Gross equity: cash + sum(qty * mid_price)
  - Net equity: gross - cumulative fees (already deducted from cash, but tracked separately)

Writes enhanced pnl_daily snapshots with gross_equity, fees_usd, positions_count.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PnlSnapshot:
    date: str
    gross_equity: float
    realized_pnl: float
    unrealized_pnl: float
    fees_usd: float
    positions_count: int
    cash_usd: float


class PnlService:
    """Computes and persists P&L snapshots."""

    def __init__(self, repository: Any, mode: str = "paper"):
        self.repo = repository
        self.mode = mode

    def compute_snapshot(self, cash_usd: float, focus_prices: dict[str, float]) -> PnlSnapshot:
        """Compute a full P&L snapshot.

        Args:
            cash_usd: Current USD cash balance.
            focus_prices: Dict of symbol → mid price from market_snapshot_focus.

        Returns:
            PnlSnapshot with all computed fields.
        """
        positions = self.repo.list_positions(self.mode)
        positions_count = len(positions)

        # Unrealized P&L and crypto value
        unrealized_pnl = 0.0
        crypto_value = 0.0

        for pos in positions:
            symbol = pos.get("symbol", "")
            qty = float(pos.get("qty", 0))
            avg_cost = float(pos.get("avg_cost", 0))
            mid = focus_prices.get(symbol, 0.0)

            if qty > 0 and mid > 0:
                pos_value = qty * mid
                crypto_value += pos_value
                unrealized_pnl += (mid - avg_cost) * qty

        # Gross equity = cash + crypto holdings at market value
        gross_equity = cash_usd + crypto_value

        # Realized P&L from fills
        realized_pnl = self.repo.get_realized_pnl(self.mode)

        # Cumulative fees
        fees_usd = self.repo.get_cumulative_fees(self.mode)

        return PnlSnapshot(
            date=str(date.today()),
            gross_equity=round(gross_equity, 4),
            realized_pnl=round(realized_pnl, 4),
            unrealized_pnl=round(unrealized_pnl, 4),
            fees_usd=round(fees_usd, 4),
            positions_count=positions_count,
            cash_usd=round(cash_usd, 4),
        )

    def write_snapshot(self, snap: PnlSnapshot) -> None:
        """Persist a P&L snapshot to pnl_daily."""
        try:
            self.repo.upsert_pnl_daily({
                "date": snap.date,
                "instance_id": "default",
                "equity": snap.gross_equity,
                "gross_equity": snap.gross_equity,
                "daily_pnl": snap.realized_pnl,
                "drawdown": 0,
                "cash_buffer_pct": (snap.cash_usd / snap.gross_equity * 100) if snap.gross_equity > 0 else 100,
                "day_trades_used": 0,
                "realized_pnl": snap.realized_pnl,
                "unrealized_pnl": snap.unrealized_pnl,
                "fees_usd": snap.fees_usd,
                "positions_count": snap.positions_count,
                "mode": self.mode,
            })
        except Exception as e:
            logger.error("PnL snapshot write error: %s", e)

    def compute_and_write(self, cash_usd: float, focus_prices: dict[str, float]) -> PnlSnapshot:
        """Convenience: compute + persist in one call."""
        snap = self.compute_snapshot(cash_usd, focus_prices)
        self.write_snapshot(snap)
        return snap

    def get_position_pnl(self, symbol: str, mid_price: float) -> dict[str, Any]:
        """Get P&L breakdown for a single position.

        Returns dict with qty, avg_cost, market_value, unrealized_pnl, unrealized_pnl_pct.
        """
        pos = self.repo.get_position(symbol, self.mode)
        if not pos:
            return {"symbol": symbol, "qty": 0, "avg_cost": 0, "market_value": 0,
                    "unrealized_pnl": 0, "unrealized_pnl_pct": 0}

        qty = float(pos.get("qty", 0))
        avg_cost = float(pos.get("avg_cost", 0))
        market_value = qty * mid_price if mid_price > 0 else 0
        cost_basis = qty * avg_cost
        unrealized = market_value - cost_basis
        pct = (unrealized / cost_basis * 100) if cost_basis > 0 else 0

        return {
            "symbol": symbol,
            "qty": qty,
            "avg_cost": round(avg_cost, 8),
            "market_value": round(market_value, 4),
            "unrealized_pnl": round(unrealized, 4),
            "unrealized_pnl_pct": round(pct, 2),
        }
