"""Configuration for the Market Data WS service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class MarketDataConfig:
    """Config for market data WebSocket pipeline."""

    # Focus universe flush interval (ms)
    focus_flush_ms: int = int(os.getenv("MD_FOCUS_FLUSH_MS", "1000"))

    # Scout universe flush interval (ms)
    scout_flush_ms: int = int(os.getenv("MD_SCOUT_FLUSH_MS", "30000"))

    # Sparkline point interval (seconds)
    sparkline_interval_sec: int = int(os.getenv("MD_SPARKLINE_INTERVAL", "900"))  # 15 min

    # Mover detection thresholds
    mover_momentum_1h_pct: float = float(os.getenv("MD_MOVER_MOMENTUM_PCT", "3.0"))
    mover_volume_accel: float = float(os.getenv("MD_MOVER_VOLUME_ACCEL", "2.0"))
    mover_spread_max_pct: float = float(os.getenv("MD_MOVER_SPREAD_MAX_PCT", "1.0"))

    # How long a mover stays in focus before demotion (minutes)
    mover_focus_minutes: int = int(os.getenv("MD_MOVER_FOCUS_MIN", "30"))

    # Catalog refresh interval (hours)
    catalog_refresh_hours: float = float(os.getenv("MD_CATALOG_REFRESH_HOURS", "24"))

    # Max pairs to subscribe to at once (Kraken limit)
    max_ws_pairs: int = int(os.getenv("MD_MAX_WS_PAIRS", "500"))

    # Default focus symbols (always in focus)
    default_focus: list[str] = field(default_factory=lambda: [
        s.strip() for s in os.getenv(
            "MD_DEFAULT_FOCUS", "BTC-USD,ETH-USD,SOL-USD,DOGE-USD,XRP-USD"
        ).split(",") if s.strip()
    ])

    # Quote currency filter (only USD pairs for now)
    quote_currency: str = os.getenv("MD_QUOTE_CURRENCY", "USD")
