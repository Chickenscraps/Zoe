"""
Circuit breakers for the Edge Factory trading loop.

Implements safety halts per research requirements:
  [AA] §7.3 — Daily drawdown kill, consecutive loss halt, spread filter
  [HL] §Self-Heal — Stale quote halt, spread blowout halt

Each breaker can block entries, exits, or both. The orchestrator
checks all breakers before processing signals.

Usage:
    cb_manager = CircuitBreakerManager(config)

    # In tick():
    active_breakers = cb_manager.check_all(context)
    if any(b.blocks_entries for b in active_breakers):
        skip new entries...
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreaker:
    """A single active circuit breaker."""
    name: str
    severity: str  # "warning", "critical"
    message: str
    blocks_entries: bool = True
    blocks_exits: bool = False
    triggered_at: float = field(default_factory=time.monotonic)


class CircuitBreakerManager:
    """
    Manages all circuit breakers. Evaluated once per tick.

    Breakers:
    1. daily_drawdown_soft  — 5% rolling 24h DD → pause entries, alert
    2. consecutive_loss     — 5 consecutive losses → 4h cooldown
    3. spread_blowout       — BTC spread > 1% for 10 ticks → DEFENSIVE mode
    4. stale_quote          — quote age > 1000ms → 5s market wait
    """

    def __init__(
        self,
        dd_soft_pct: float = 5.0,
        dd_hard_pct: float = 20.0,
        max_consecutive_losses: int = 5,
        loss_cooldown_hours: float = 4.0,
        spread_blowout_pct: float = 1.0,
        spread_blowout_ticks: int = 10,
        spread_recovery_pct: float = 0.5,
        spread_recovery_ticks: int = 5,
        stale_quote_ms: float = 1000.0,
        stale_market_wait_s: float = 5.0,
    ):
        # Daily drawdown
        self.dd_soft_pct = dd_soft_pct
        self.dd_hard_pct = dd_hard_pct

        # Consecutive losses
        self.max_consecutive_losses = max_consecutive_losses
        self.loss_cooldown_hours = loss_cooldown_hours
        self._loss_cooldown_until: float = 0.0  # monotonic
        self._consecutive_losses: int = 0

        # Spread blowout
        self.spread_blowout_pct = spread_blowout_pct
        self.spread_blowout_ticks = spread_blowout_ticks
        self.spread_recovery_pct = spread_recovery_pct
        self.spread_recovery_ticks = spread_recovery_ticks
        self._spread_blowout_count: int = 0
        self._spread_recovery_count: int = 0
        self._in_defensive_mode: bool = False

        # Stale quote
        self.stale_quote_ms = stale_quote_ms
        self.stale_market_wait_s = stale_market_wait_s
        self._stale_detected: bool = False

        logger.info(
            "CircuitBreakerManager initialized: DD_soft=%.1f%%, DD_hard=%.1f%%, "
            "max_losses=%d, spread_blowout=%.1f%%",
            dd_soft_pct, dd_hard_pct, max_consecutive_losses, spread_blowout_pct,
        )

    def check_all(
        self,
        equity: float,
        equity_hwm: float,
        consecutive_losses: int,
        btc_spread_pct: float,
        quote_age_ms: float,
        daily_dd_pct: Optional[float] = None,
    ) -> list[CircuitBreaker]:
        """
        Evaluate all circuit breakers and return active ones.

        Args:
            equity: Current portfolio equity
            equity_hwm: High water mark (rolling 24h)
            consecutive_losses: Number of consecutive closed losses
            btc_spread_pct: Current BTC-USD bid-ask spread as %
            quote_age_ms: Age of latest quote in milliseconds
            daily_dd_pct: Pre-computed 24h drawdown % (optional, computed if None)
        """
        active: list[CircuitBreaker] = []

        # ── 1. Daily Drawdown ───────────────────────────────
        if daily_dd_pct is None and equity_hwm > 0:
            daily_dd_pct = ((equity_hwm - equity) / equity_hwm) * 100.0

        if daily_dd_pct is not None:
            if daily_dd_pct >= self.dd_hard_pct:
                active.append(CircuitBreaker(
                    name="daily_drawdown_hard",
                    severity="critical",
                    message=f"HARD KILL: 24h drawdown {daily_dd_pct:.1f}% >= {self.dd_hard_pct}%",
                    blocks_entries=True,
                    blocks_exits=False,  # Allow exits to close positions
                ))
            elif daily_dd_pct >= self.dd_soft_pct:
                active.append(CircuitBreaker(
                    name="daily_drawdown_soft",
                    severity="warning",
                    message=f"Soft pause: 24h drawdown {daily_dd_pct:.1f}% >= {self.dd_soft_pct}%",
                    blocks_entries=True,
                    blocks_exits=False,
                ))

        # ── 2. Consecutive Loss Cooldown ────────────────────
        self._consecutive_losses = consecutive_losses

        if consecutive_losses >= self.max_consecutive_losses:
            now = time.monotonic()
            if self._loss_cooldown_until == 0.0:
                # Start cooldown
                self._loss_cooldown_until = now + (self.loss_cooldown_hours * 3600)
                logger.warning(
                    "Consecutive loss halt: %d losses → %.0fh cooldown",
                    consecutive_losses, self.loss_cooldown_hours,
                )

            if now < self._loss_cooldown_until:
                remaining_min = (self._loss_cooldown_until - now) / 60
                active.append(CircuitBreaker(
                    name="consecutive_loss",
                    severity="warning",
                    message=f"Cooldown: {consecutive_losses} consecutive losses, "
                            f"{remaining_min:.0f}min remaining",
                    blocks_entries=True,
                    blocks_exits=False,
                ))
            else:
                # Cooldown expired
                self._loss_cooldown_until = 0.0
        else:
            # Reset cooldown if losses streak broken
            self._loss_cooldown_until = 0.0

        # ── 3. Spread Blowout (BTC benchmark) ──────────────
        if btc_spread_pct >= self.spread_blowout_pct:
            self._spread_blowout_count += 1
            self._spread_recovery_count = 0
        elif btc_spread_pct <= self.spread_recovery_pct:
            self._spread_recovery_count += 1
            self._spread_blowout_count = max(0, self._spread_blowout_count - 1)
        else:
            self._spread_recovery_count = 0

        if self._spread_blowout_count >= self.spread_blowout_ticks:
            self._in_defensive_mode = True

        if self._in_defensive_mode:
            if self._spread_recovery_count >= self.spread_recovery_ticks:
                self._in_defensive_mode = False
                self._spread_blowout_count = 0
                logger.info("Spread blowout recovered — exiting DEFENSIVE mode")
            else:
                active.append(CircuitBreaker(
                    name="spread_blowout",
                    severity="warning",
                    message=f"DEFENSIVE: BTC spread {btc_spread_pct:.2f}% "
                            f"(>{self.spread_blowout_pct}% for "
                            f"{self._spread_blowout_count} ticks)",
                    blocks_entries=True,
                    blocks_exits=False,
                ))

        # ── 4. Stale Quote Detection ───────────────────────
        if quote_age_ms > self.stale_quote_ms:
            self._stale_detected = True
            active.append(CircuitBreaker(
                name="stale_quote",
                severity="warning",
                message=f"Stale quote: {quote_age_ms:.0f}ms old "
                        f"(>{self.stale_quote_ms:.0f}ms) — "
                        f"market wait {self.stale_market_wait_s}s",
                blocks_entries=True,
                blocks_exits=False,  # Don't block exits on stale data
            ))
        else:
            self._stale_detected = False

        return active

    @property
    def is_defensive(self) -> bool:
        """True if spread blowout DEFENSIVE mode is active."""
        return self._in_defensive_mode

    @property
    def is_stale(self) -> bool:
        """True if latest quote is stale."""
        return self._stale_detected

    def get_status(self) -> dict:
        """Return status dict for observability."""
        return {
            "consecutive_losses": self._consecutive_losses,
            "loss_cooldown_active": self._loss_cooldown_until > time.monotonic(),
            "defensive_mode": self._in_defensive_mode,
            "spread_blowout_ticks": self._spread_blowout_count,
            "stale_quote": self._stale_detected,
        }
