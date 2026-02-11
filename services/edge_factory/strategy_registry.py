from __future__ import annotations

from typing import Any


class StrategyRegistry:
    """
    Registry for strategy configurations.

    V1 has one strategy: "regime_adaptive_sniper".
    Designed for future expansion with additional strategies.
    """

    STRATEGIES: dict[str, dict[str, Any]] = {
        "regime_adaptive_sniper": {
            "description": "Regime-adaptive long-only strategy using attention + funding rate signals",
            "entry_features": [
                "trend_z_score_14d",
                "funding_rate_basis",
                "vwap_distance",
                "corwin_schultz_spread",
                "portfolio_heat",
                "consecutive_loss_count",
            ],
            "regime_features": [
                "amihud_spike_z",
                "amihud_illiquidity",
            ],
            "sizing_features": [
                "expected_move_pct",
            ],
            "exit_features": [
                "drawdown_current",
                "garman_klass_vol",
            ],
            "regime_filter": True,
            "position_sizing": "half_kelly",
            "directions": ["long"],
            "min_features_required": 4,  # At least 4 of 6 entry features needed
        },
    }

    @classmethod
    def get(cls, name: str) -> dict[str, Any] | None:
        return cls.STRATEGIES.get(name)

    @classmethod
    def list_strategies(cls) -> list[str]:
        return list(cls.STRATEGIES.keys())

    @classmethod
    def validate_features(cls, strategy_name: str, features: dict[str, float]) -> bool:
        """Check if enough entry features are available for a strategy."""
        strategy = cls.get(strategy_name)
        if not strategy:
            return False
        required = strategy["entry_features"]
        available = sum(1 for f in required if f in features)
        return available >= strategy["min_features_required"]
