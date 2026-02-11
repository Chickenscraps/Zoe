"""
Position Sizer — risk-based sizing for crypto trades.

Calculates the notional order size given:
  - Account equity (from paper broker or Robinhood reconciliation)
  - Risk per trade (from config, as fraction of equity)
  - Entry price and stop loss price (from TradeIntent)
  - Maximum per-trade notional cap (safety limit)

Uses fixed-fractional risk model:
  size_usd = (equity × risk_fraction) / abs(entry - stop_loss) × entry
  capped at max_notional_per_trade and max_equity_pct × equity

This is conservative by design — no Kelly criterion, no leverage.
"""

from __future__ import annotations

import logging
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Load config ─────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

def _load_sizing_config() -> Dict[str, Any]:
    """Load the position sizing section from config.yaml."""
    try:
        with open(_CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("position_sizing", {})
    except Exception:
        return {}


@dataclass
class SizingResult:
    """Result of a position sizing calculation."""
    notional_usd: float         # Dollar amount to trade
    quantity: float             # Crypto quantity (notional / entry_price)
    risk_usd: float             # Dollar risk if stopped out
    risk_pct: float             # Risk as % of equity
    r_multiple_tp: float        # Reward-to-risk ratio (TP side)
    reason: str                 # Human-readable sizing rationale
    capped: bool                # Whether the size was capped by a safety limit

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notional_usd": round(self.notional_usd, 2),
            "quantity": round(self.quantity, 8),
            "risk_usd": round(self.risk_usd, 2),
            "risk_pct": round(self.risk_pct, 4),
            "r_multiple_tp": round(self.r_multiple_tp, 2),
            "reason": self.reason,
            "capped": self.capped,
        }


class PositionSizer:
    """
    Fixed-fractional risk-based position sizer.

    Risk model:
        risk_per_unit = |entry_price - sl_price|
        units = (equity × risk_fraction) / risk_per_unit
        notional = units × entry_price

    Safety caps:
        1. max_notional_per_trade (absolute dollar cap)
        2. max_equity_pct × equity (percentage cap)
        3. min_notional (floor — too small trades are rejected)
    """

    def __init__(
        self,
        risk_fraction: float = 0.02,
        max_notional_per_trade: float = 500.0,
        max_equity_pct: float = 0.25,
        min_notional: float = 10.0,
        score_scaling: bool = True,
    ):
        self.risk_fraction = risk_fraction
        self.max_notional_per_trade = max_notional_per_trade
        self.max_equity_pct = max_equity_pct
        self.min_notional = min_notional
        self.score_scaling = score_scaling

    @classmethod
    def from_config(cls) -> "PositionSizer":
        """Create a PositionSizer from config.yaml values."""
        cfg = _load_sizing_config()
        trading_cfg = {}
        try:
            with open(_CONFIG_PATH, "r") as f:
                full_cfg = yaml.safe_load(f) or {}
            trading_cfg = full_cfg.get("trading", {})
        except Exception:
            pass

        # Position sizing config with sensible defaults
        risk_fraction = cfg.get("risk_fraction", 0.02)  # 2% of equity per trade
        max_notional = cfg.get(
            "max_notional_per_trade",
            trading_cfg.get("max_risk_per_trade", 100.0) * 5,  # 5x the risk cap as notional cap
        )
        max_equity_pct = cfg.get("max_equity_pct", 0.25)  # max 25% of equity per trade
        min_notional = cfg.get("min_notional", 10.0)  # don't bother with <$10 trades
        score_scaling = cfg.get("score_scaling", True)

        return cls(
            risk_fraction=risk_fraction,
            max_notional_per_trade=max_notional,
            max_equity_pct=max_equity_pct,
            min_notional=min_notional,
            score_scaling=score_scaling,
        )

    def calculate(
        self,
        equity: float,
        entry_price: float,
        sl_price: float,
        tp_price: float = 0.0,
        score: int = 100,
    ) -> Optional[SizingResult]:
        """
        Calculate position size for a trade.

        Parameters
        ----------
        equity : float
            Current account equity in USD.
        entry_price : float
            Planned entry price.
        sl_price : float
            Stop loss price.
        tp_price : float
            Take profit price (for R:R calculation).
        score : int
            Bounce score (0-100). Higher scores get full sizing,
            lower scores get reduced sizing.

        Returns
        -------
        SizingResult or None if the trade should be skipped.
        """
        if equity <= 0 or entry_price <= 0:
            logger.warning("Invalid equity (%.2f) or entry_price (%.2f)", equity, entry_price)
            return None

        # Risk per unit of crypto
        risk_per_unit = abs(entry_price - sl_price)
        if risk_per_unit <= 0:
            logger.warning("Zero risk per unit (entry=%.6f, sl=%.6f)", entry_price, sl_price)
            return None

        # Base risk budget = equity × risk_fraction
        risk_budget_usd = equity * self.risk_fraction

        # Score scaling: linearly scale between 50% (score=70) and 100% (score=100)
        if self.score_scaling and score < 100:
            # Map score 70-100 → 0.5-1.0 multiplier
            score_mult = max(0.5, min(1.0, (score - 40) / 60.0))
            risk_budget_usd *= score_mult

        # Units = risk_budget / risk_per_unit
        units = risk_budget_usd / risk_per_unit
        notional = units * entry_price

        # Apply caps
        capped = False
        cap_reason = ""

        # Cap 1: absolute notional limit
        if notional > self.max_notional_per_trade:
            notional = self.max_notional_per_trade
            units = notional / entry_price
            capped = True
            cap_reason = f"capped at max_notional=${self.max_notional_per_trade:.0f}"

        # Cap 2: max equity percentage
        max_equity_notional = equity * self.max_equity_pct
        if notional > max_equity_notional:
            notional = max_equity_notional
            units = notional / entry_price
            capped = True
            cap_reason = f"capped at {self.max_equity_pct*100:.0f}% equity"

        # Floor check
        if notional < self.min_notional:
            logger.info(
                "Position too small ($%.2f < min $%.2f) — skipping",
                notional,
                self.min_notional,
            )
            return None

        # Actual risk
        actual_risk_usd = units * risk_per_unit
        actual_risk_pct = actual_risk_usd / equity if equity > 0 else 0

        # R:R
        r_multiple_tp = 0.0
        if tp_price > 0 and risk_per_unit > 0:
            reward_per_unit = abs(tp_price - entry_price)
            r_multiple_tp = reward_per_unit / risk_per_unit

        reason = (
            f"${notional:.2f} notional ({units:.6f} units @ ${entry_price:,.2f}), "
            f"risk=${actual_risk_usd:.2f} ({actual_risk_pct*100:.2f}% of equity), "
            f"R:R={r_multiple_tp:.1f}:1"
        )
        if capped:
            reason += f" [{cap_reason}]"

        return SizingResult(
            notional_usd=notional,
            quantity=units,
            risk_usd=actual_risk_usd,
            risk_pct=actual_risk_pct,
            r_multiple_tp=r_multiple_tp,
            reason=reason,
            capped=capped,
        )


# Module-level singleton
position_sizer = PositionSizer.from_config()
