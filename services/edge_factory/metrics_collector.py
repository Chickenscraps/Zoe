"""
Observability metrics collector for the Edge Factory.

Tracks high-resolution execution metrics per tick and persists them
to the local event store for eventual flush to Supabase.

Metrics tracked:
  - stale_quote_rate: % of ticks with quote age > 1000ms
  - implementation_shortfall_bps: Rolling avg IS
  - spread_blowout_rate: % of ticks with BTC spread > 0.5%
  - sync_lag_ms: Time from local write to Supabase confirmation
  - rejection_rate: % of order attempts that fail/timeout
  - loop_jitter_p99_ms: 99th percentile tick interval variance
  - fill_rate: % of limit orders that fill vs cancel

References:
  [HL] §Monitoring — persist high-resolution execution metrics
  [AA] §8.1 — real-time telemetry
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Rolling window sizes
TICK_WINDOW = 100  # ticks for rate metrics
FILL_WINDOW = 50   # fills for IS averaging
JITTER_WINDOW = 100  # ticks for jitter calculation


@dataclass
class FillRecord:
    """Record of a single fill for IS tracking."""
    symbol: str
    side: str
    decision_price: float
    fill_price: float
    is_bps: float
    spread_at_decision_pct: float
    timestamp: float = field(default_factory=time.monotonic)


class MetricsCollector:
    """
    Collects and computes trading metrics.

    Call record_tick() at the end of each tick cycle.
    Call record_fill() after each order fill.
    Call get_snapshot() to emit metrics to local store.
    """

    def __init__(self, emit_interval_ticks: int = 10):
        self.emit_interval = emit_interval_ticks
        self._tick_count: int = 0

        # Tick-level metrics (rolling window)
        self._tick_timestamps: deque[float] = deque(maxlen=JITTER_WINDOW)
        self._stale_ticks: deque[bool] = deque(maxlen=TICK_WINDOW)
        self._spread_blowout_ticks: deque[bool] = deque(maxlen=TICK_WINDOW)

        # Fill-level metrics
        self._fill_records: deque[FillRecord] = deque(maxlen=FILL_WINDOW)
        self._order_attempts: int = 0
        self._order_rejections: int = 0
        self._order_fills: int = 0
        self._order_cancels: int = 0

        # Sync lag tracking
        self._last_sync_lag_ms: float = 0.0

        logger.info("MetricsCollector initialized (emit every %d ticks)", emit_interval_ticks)

    def record_tick(
        self,
        quote_age_ms: float,
        btc_spread_pct: float,
        tick_duration_ms: Optional[float] = None,
    ) -> None:
        """Record metrics for a single tick cycle."""
        now = time.monotonic()
        self._tick_count += 1

        self._tick_timestamps.append(now)
        self._stale_ticks.append(quote_age_ms > 1000.0)
        self._spread_blowout_ticks.append(btc_spread_pct > 0.5)

    def record_fill(
        self,
        symbol: str,
        side: str,
        decision_price: float,
        fill_price: float,
        spread_at_decision_pct: float = 0.0,
    ) -> FillRecord:
        """Record a fill and compute implementation shortfall."""
        if decision_price <= 0:
            is_bps = 0.0
        else:
            is_bps = ((fill_price - decision_price) / decision_price) * 10000.0

        record = FillRecord(
            symbol=symbol,
            side=side,
            decision_price=decision_price,
            fill_price=fill_price,
            is_bps=is_bps,
            spread_at_decision_pct=spread_at_decision_pct,
        )
        self._fill_records.append(record)
        self._order_fills += 1

        logger.info(
            "Fill recorded: %s %s decision=%.4f fill=%.4f IS=%.1f bps",
            side, symbol, decision_price, fill_price, is_bps,
        )
        return record

    def record_order_attempt(self) -> None:
        """Record an order submission attempt."""
        self._order_attempts += 1

    def record_order_rejection(self) -> None:
        """Record an order rejection/timeout."""
        self._order_rejections += 1

    def record_order_cancel(self) -> None:
        """Record an order cancel (unfilled)."""
        self._order_cancels += 1

    def record_sync_lag(self, lag_ms: float) -> None:
        """Record the latest sync lag measurement."""
        self._last_sync_lag_ms = lag_ms

    def should_emit(self) -> bool:
        """True if it's time to emit a metrics snapshot."""
        return self._tick_count > 0 and self._tick_count % self.emit_interval == 0

    def get_snapshot(self) -> dict:
        """Compute and return the current metrics snapshot."""
        snapshot = {}

        # ── Stale Quote Rate ────────────────────────────────
        if self._stale_ticks:
            stale_count = sum(1 for s in self._stale_ticks if s)
            snapshot["stale_quote_rate"] = round(
                (stale_count / len(self._stale_ticks)) * 100, 1
            )
        else:
            snapshot["stale_quote_rate"] = 0.0

        # ── Implementation Shortfall (rolling avg) ──────────
        if self._fill_records:
            # Average absolute IS (both positive and negative)
            avg_is = sum(abs(f.is_bps) for f in self._fill_records) / len(self._fill_records)
            snapshot["implementation_shortfall_bps"] = round(avg_is, 2)

            # Directional IS (positive = slippage, negative = improvement)
            avg_directional_is = sum(f.is_bps for f in self._fill_records) / len(self._fill_records)
            snapshot["implementation_shortfall_directional_bps"] = round(avg_directional_is, 2)
        else:
            snapshot["implementation_shortfall_bps"] = 0.0
            snapshot["implementation_shortfall_directional_bps"] = 0.0

        # ── Spread Blowout Rate ─────────────────────────────
        if self._spread_blowout_ticks:
            blowout_count = sum(1 for s in self._spread_blowout_ticks if s)
            snapshot["spread_blowout_rate"] = round(
                (blowout_count / len(self._spread_blowout_ticks)) * 100, 1
            )
        else:
            snapshot["spread_blowout_rate"] = 0.0

        # ── Sync Lag ────────────────────────────────────────
        snapshot["sync_lag_ms"] = round(self._last_sync_lag_ms, 0)

        # ── Rejection Rate ──────────────────────────────────
        if self._order_attempts > 0:
            snapshot["rejection_rate"] = round(
                (self._order_rejections / self._order_attempts) * 100, 1
            )
        else:
            snapshot["rejection_rate"] = 0.0

        # ── Fill Rate ───────────────────────────────────────
        total_outcomes = self._order_fills + self._order_cancels
        if total_outcomes > 0:
            snapshot["fill_rate"] = round(
                (self._order_fills / total_outcomes) * 100, 1
            )
        else:
            snapshot["fill_rate"] = 0.0

        # ── Loop Jitter P99 ─────────────────────────────────
        if len(self._tick_timestamps) >= 3:
            intervals = []
            ts_list = list(self._tick_timestamps)
            for i in range(1, len(ts_list)):
                intervals.append((ts_list[i] - ts_list[i - 1]) * 1000)  # ms

            if intervals:
                intervals.sort()
                p99_idx = min(int(len(intervals) * 0.99), len(intervals) - 1)
                snapshot["loop_jitter_p99_ms"] = round(intervals[p99_idx], 1)

                # Also compute median for context
                median_idx = len(intervals) // 2
                snapshot["loop_interval_median_ms"] = round(intervals[median_idx], 1)
            else:
                snapshot["loop_jitter_p99_ms"] = 0.0
                snapshot["loop_interval_median_ms"] = 0.0
        else:
            snapshot["loop_jitter_p99_ms"] = 0.0
            snapshot["loop_interval_median_ms"] = 0.0

        # ── Counts ──────────────────────────────────────────
        snapshot["total_ticks"] = self._tick_count
        snapshot["total_fills"] = self._order_fills
        snapshot["total_order_attempts"] = self._order_attempts
        snapshot["total_order_rejections"] = self._order_rejections

        return snapshot

    def get_latest_is_bps(self, n: int = 20) -> float:
        """Return the average IS of the last N fills."""
        recent = list(self._fill_records)[-n:]
        if not recent:
            return 0.0
        return sum(f.is_bps for f in recent) / len(recent)
