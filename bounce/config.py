"""
Configuration dataclass for the bounce catcher module.
Loaded from the ``bounce:`` section of ``config.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CapitulationConfig:
    atr_mult: float = 2.5
    vol_mult: float = 2.0
    lower_wick_min: float = 0.45


@dataclass
class StabilizationConfig:
    confirmations_required: int = 2
    higher_lows_k: int = 4
    rsi_reclaim: float = 30.0
    funding_support_max_8h: float = 0.001
    allow_missing_altdata: bool = True


@dataclass
class ExecutionConfig:
    tp_pct: float = 0.045
    time_stop_hours: int = 12
    sl_atr_mult: float = 1.5
    max_spread_pct_to_trade: float = 0.003
    entry_style: str = "retest"          # 'retest' | 'breakout'
    sl_hard_pct: float = 0.03            # hard -3% for tiny accounts


@dataclass
class BounceScoreConfig:
    min_score: int = 70


@dataclass
class AlertConfig:
    throttle_minutes: int = 30


@dataclass
class BounceConfig:
    enabled: bool = False                 # shadow mode by default
    universe: List[str] = field(default_factory=lambda: ["BTC-USD", "ETH-USD"])
    atr_len: int = 14
    vol_ma_len: int = 20
    capitulation: CapitulationConfig = field(default_factory=CapitulationConfig)
    stabilization: StabilizationConfig = field(default_factory=StabilizationConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    scoring: BounceScoreConfig = field(default_factory=BounceScoreConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)

    # Guardrail knobs
    vol_halt_24h_range: float = 0.05     # if 24h range/open > 5%, halt entries
    weekend_dampener: bool = False        # reduce confidence on weekends

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BounceConfig":
        if not d:
            return cls()
        return cls(
            enabled=d.get("enabled", False),
            universe=d.get("universe", ["BTC-USD", "ETH-USD"]),
            atr_len=d.get("atr_len", 14),
            vol_ma_len=d.get("vol_ma_len", 20),
            capitulation=CapitulationConfig(**d["capitulation"]) if "capitulation" in d else CapitulationConfig(),
            stabilization=StabilizationConfig(**d["stabilization"]) if "stabilization" in d else StabilizationConfig(),
            execution=ExecutionConfig(**d["execution"]) if "execution" in d else ExecutionConfig(),
            scoring=BounceScoreConfig(**d["scoring"]) if "scoring" in d else BounceScoreConfig(),
            alerts=AlertConfig(**d["alerts"]) if "alerts" in d else AlertConfig(),
            vol_halt_24h_range=d.get("vol_halt_24h_range", 0.05),
            weekend_dampener=d.get("weekend_dampener", False),
        )
