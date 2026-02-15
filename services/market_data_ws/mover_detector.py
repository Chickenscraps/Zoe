"""Mover Detector — identifies momentum/volume breakouts from scout data.

On each scout flush, checks for:
1. 1h momentum (price change % using sparkline history)
2. Volume acceleration (current vs 24h average)
3. Spread guard (reject if spread > threshold)

Triggers promotion to focus universe when thresholds exceeded.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .coalescer import TickerSnapshot
from .config import MarketDataConfig

logger = logging.getLogger(__name__)


class MoverDetector:
    """Detects momentum/volume movers from scout universe data."""

    def __init__(self, config: MarketDataConfig):
        self.config = config

        # Price history for momentum calculation: symbol -> [(ts, mid)]
        self._price_history: dict[str, list[tuple[datetime, float]]] = {}
        self._max_history = 120  # Keep ~2h of data points

        # Volume baselines for acceleration detection: symbol -> [volume_24h...]
        self._volume_baselines: dict[str, list[float]] = {}

    def record_price(self, symbol: str, mid: float) -> None:
        """Record a price point for momentum calculation."""
        if mid <= 0:
            return
        now = datetime.now(timezone.utc)
        history = self._price_history.setdefault(symbol, [])
        history.append((now, mid))

        # Trim old entries
        if len(history) > self._max_history:
            cutoff = now - timedelta(hours=2)
            self._price_history[symbol] = [(t, p) for t, p in history if t > cutoff]

    def check_movers(self, snapshots: list[TickerSnapshot]) -> list[dict[str, Any]]:
        """Check all snapshots for mover conditions.

        Returns list of mover events (symbol, event_type, magnitude, direction).
        """
        events: list[dict[str, Any]] = []

        for snap in snapshots:
            self.record_price(snap.symbol, snap.mid)

            # Skip symbols with wide spreads (likely illiquid)
            if snap.spread_pct > self.config.mover_spread_max_pct:
                continue

            # Check 1h momentum
            momentum = self._compute_momentum_1h(snap.symbol, snap.mid)
            if momentum is not None and abs(momentum) >= self.config.mover_momentum_1h_pct:
                events.append({
                    "symbol": snap.symbol,
                    "event_type": "momentum_1h",
                    "magnitude": abs(momentum),
                    "direction": "up" if momentum > 0 else "down",
                    "metadata": {
                        "momentum_pct": round(momentum, 2),
                        "current_mid": float(snap.mid),
                        "spread_pct": float(snap.spread_pct),
                    },
                })

            # Check volume acceleration
            if snap.volume_24h > 0:
                vol_accel = self._compute_volume_accel(snap.symbol, snap.volume_24h)
                if vol_accel is not None and vol_accel >= self.config.mover_volume_accel:
                    events.append({
                        "symbol": snap.symbol,
                        "event_type": "volume_accel",
                        "magnitude": round(vol_accel, 2),
                        "direction": "up",
                        "metadata": {
                            "volume_24h": float(snap.volume_24h),
                            "accel_ratio": round(vol_accel, 2),
                        },
                    })

        return events

    def _compute_momentum_1h(self, symbol: str, current_mid: float) -> float | None:
        """Compute 1-hour price change percentage."""
        history = self._price_history.get(symbol, [])
        if not history or current_mid <= 0:
            return None

        # Find price from ~1h ago
        target = datetime.now(timezone.utc) - timedelta(hours=1)
        best_match: tuple[datetime, float] | None = None

        for ts, price in history:
            if ts <= target:
                if best_match is None or ts > best_match[0]:
                    best_match = (ts, price)

        if best_match is None or best_match[1] <= 0:
            return None

        # Must be within 15-min window of target to be valid
        if abs((best_match[0] - target).total_seconds()) > 900:
            return None

        return (current_mid - best_match[1]) / best_match[1] * 100

    def _compute_volume_accel(self, symbol: str, current_volume: float) -> float | None:
        """Compute volume acceleration ratio.

        Tracks a rolling baseline of volume_24h snapshots per symbol.
        When the current volume_24h is significantly higher than the
        rolling average, it signals unusual trading activity.

        Returns the acceleration ratio (current / baseline), or None
        if insufficient baseline data exists.
        """
        if current_volume <= 0:
            return None

        baseline = self._volume_baselines.get(symbol)
        if baseline is None:
            # First observation — start tracking
            self._volume_baselines[symbol] = [current_volume]
            return None

        # Add to baseline
        baseline.append(current_volume)

        # Keep only last N observations (trim to max)
        max_baseline = 60  # ~30 min at 30s scout interval
        if len(baseline) > max_baseline:
            self._volume_baselines[symbol] = baseline[-max_baseline:]
            baseline = self._volume_baselines[symbol]

        # Need at least 5 data points for a meaningful baseline
        if len(baseline) < 5:
            return None

        # Compute rolling average (exclude the current observation)
        avg_volume = sum(baseline[:-1]) / len(baseline[:-1])
        if avg_volume <= 0:
            return None

        return current_volume / avg_volume
