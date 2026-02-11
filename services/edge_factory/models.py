from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class FeatureSnapshot:
    """A single computed feature value at a point in time."""

    symbol: str
    feature_name: str
    value: float
    computed_at: datetime = field(default_factory=_utcnow)
    source: str = ""  # "google_trends" | "okx" | "polygon" | "computed"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegimeState:
    """Market regime classification."""

    regime: str  # "low_vol_bull" | "high_vol_crash" | "transition"
    confidence: float  # 0.0 - 1.0
    detected_at: datetime = field(default_factory=_utcnow)
    features_used: dict[str, float] = field(default_factory=dict)

    def allows_trading(self) -> bool:
        return self.regime in {"low_vol_bull", "transition"}

    def sizing_multiplier(self) -> float:
        if self.regime == "low_vol_bull":
            return 1.0
        if self.regime == "transition":
            return 0.5
        return 0.0


@dataclass
class Signal:
    """A trading signal produced by the strategy engine."""

    symbol: str
    direction: str  # "long" | "short" | "hold"
    strength: float  # 0.0 - 1.0
    regime: RegimeState
    features: dict[str, float] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=_utcnow)
    strategy_name: str = "regime_adaptive_sniper"
    signal_id: str = ""


@dataclass
class EdgePosition:
    """An Edge Factory managed position (paper or live)."""

    symbol: str
    side: str = "buy"
    entry_price: float = 0.0
    entry_time: datetime = field(default_factory=_utcnow)
    size_usd: float = 0.0
    tp_price: float = 0.0
    sl_price: float = 0.0
    status: str = "pending"  # "pending" | "open" | "closed_tp" | "closed_sl" | "closed_timeout" | "closed_kill" | "closed_regime"
    exit_price: float | None = None
    exit_time: datetime | None = None
    pnl_usd: float | None = None
    signal_id: str = ""
    order_id: str | None = None
    position_id: str = ""

    def is_open(self) -> bool:
        return self.status in {"pending", "open"}

    def check_tp(self, current_price: float) -> bool:
        return current_price >= self.tp_price

    def check_sl(self, current_price: float) -> bool:
        return current_price <= self.sl_price

    def compute_pnl(self, exit_price: float) -> float:
        if self.entry_price <= 0:
            return 0.0
        qty = self.size_usd / self.entry_price
        return qty * (exit_price - self.entry_price)
