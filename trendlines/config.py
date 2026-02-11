"""
Configuration dataclass for the trendlines module.

Loaded from the ``trendlines:`` section of ``config.yaml``.  Every numeric
knob referenced in the research docs lives here with a sensible default so
the module works even when no YAML is present.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PivotConfig:
    method: str = "FRACTAL"
    k: int = 3                      # half-window for rolling fractal
    atr_len: int = 14
    atr_pivot_mult: float = 0.75    # min pivot excursion in ATR units
    max_pivots: int = 300           # bound input size for RANSAC/DBSCAN
    sources: List[str] = field(default_factory=lambda: ["wick", "body"])


@dataclass
class FittingConfig:
    method: str = "RANSAC"
    min_pivots: int = 3             # min inlier touches for a valid line
    max_lines_per_side: int = 2     # sequential-peel limit
    max_trials: int = 500
    random_state: int = 42          # determinism


@dataclass
class ToleranceConfig:
    atr_tol_mult: float = 0.35      # RANSAC residual_threshold = ATR * this
    pct_tol: float = 0.002          # fallback %-based tolerance


@dataclass
class HorizontalsConfig:
    cluster_method: str = "DBSCAN"
    eps_atr_mult: float = 0.25
    min_samples: int = 3
    min_cluster_touches: int = 3


@dataclass
class ScoringWeights:
    touches: float = 0.40
    recency: float = 0.35
    confluence: float = 0.15
    stability: float = 0.10


@dataclass
class ScoringConfig:
    min_score_to_keep: float = 60
    weights: ScoringWeights = field(default_factory=ScoringWeights)


@dataclass
class EventsConfig:
    confirm_closes_15m: int = 2
    confirm_closes_1h: int = 2
    confirm_closes_4h: int = 1
    breakout_epsilon_pct: float = 0.001


@dataclass
class TrendlinesConfig:
    enabled: bool = True
    universe: List[str] = field(default_factory=lambda: ["BTC-USD", "ETH-USD"])
    timeframes: List[str] = field(default_factory=lambda: ["15m", "1h", "4h", "1d"])
    pivots: PivotConfig = field(default_factory=PivotConfig)
    fitting: FittingConfig = field(default_factory=FittingConfig)
    tolerance: ToleranceConfig = field(default_factory=ToleranceConfig)
    horizontals: HorizontalsConfig = field(default_factory=HorizontalsConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    events: EventsConfig = field(default_factory=EventsConfig)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrendlinesConfig":
        """Build from a raw dict (e.g. parsed YAML section)."""
        if not d:
            return cls()
        return cls(
            enabled=d.get("enabled", True),
            universe=d.get("universe", cls.universe),
            timeframes=d.get("timeframes", ["15m", "1h", "4h", "1d"]),
            pivots=PivotConfig(**d["pivots"]) if "pivots" in d else PivotConfig(),
            fitting=FittingConfig(**d["fitting"]) if "fitting" in d else FittingConfig(),
            tolerance=ToleranceConfig(**d["tolerance"]) if "tolerance" in d else ToleranceConfig(),
            horizontals=HorizontalsConfig(**d["horizontals"]) if "horizontals" in d else HorizontalsConfig(),
            scoring=ScoringConfig(
                min_score_to_keep=d.get("scoring", {}).get("min_score_to_keep", 60),
                weights=ScoringWeights(**d.get("scoring", {}).get("weights", {})) if d.get("scoring", {}).get("weights") else ScoringWeights(),
            ),
            events=EventsConfig(**d["events"]) if "events" in d else EventsConfig(),
        )
