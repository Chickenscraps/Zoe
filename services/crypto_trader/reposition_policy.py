"""Reposition policy for stale/unfilled orders.

Configurable via environment variables:
  ORDER_TTL_SECONDS_ENTRY  (default: 60)
  ORDER_TTL_SECONDS_EXIT   (default: 30)
  MAX_REPRICE_ATTEMPTS     (default: 3)
  REPRICE_STEP_BPS         (default: 5)
  MAX_CROSS_SPREAD_BPS     (default: 20)
  LIQUIDITY_GUARD_SPREAD_PCT (default: 0.5)
"""
from __future__ import annotations

import os
from enum import Enum


class RepositionDecision(Enum):
    HOLD = "hold"           # keep current order, TTL not expired
    REPOSITION = "reposition"  # cancel + replace at new price
    CANCEL = "cancel"       # cancel without replacement (max reprices)
    CANCEL_LIQUIDITY = "cancel_liquidity"  # cancel due to wide spread


class RepositionPolicy:
    """Decides when and how to reposition stale orders."""

    def __init__(
        self,
        ttl_entry: int | None = None,
        ttl_exit: int | None = None,
        max_reprice_attempts: int | None = None,
        reprice_step_bps: float | None = None,
        max_cross_spread_bps: float | None = None,
        liquidity_guard_spread_pct: float | None = None,
    ):
        self.ttl_entry = ttl_entry or int(os.getenv("ORDER_TTL_SECONDS_ENTRY", "60"))
        self.ttl_exit = ttl_exit or int(os.getenv("ORDER_TTL_SECONDS_EXIT", "30"))
        self.max_reprice_attempts = max_reprice_attempts or int(os.getenv("MAX_REPRICE_ATTEMPTS", "3"))
        self.reprice_step_bps = reprice_step_bps or float(os.getenv("REPRICE_STEP_BPS", "5"))
        self.max_cross_spread_bps = max_cross_spread_bps or float(os.getenv("MAX_CROSS_SPREAD_BPS", "20"))
        self.liquidity_guard_spread_pct = liquidity_guard_spread_pct or float(os.getenv("LIQUIDITY_GUARD_SPREAD_PCT", "0.5"))

    def ttl_for(self, side: str, purpose: str = "entry") -> int:
        """Get TTL in seconds based on side/purpose."""
        if purpose == "exit" or side == "sell":
            return self.ttl_exit
        return self.ttl_entry

    def should_reposition(
        self,
        *,
        side: str,
        replace_count: int,
        current_limit: float | None,
        bid: float,
        ask: float,
        spread_pct: float,
    ) -> RepositionDecision:
        """Decide what to do with a stale order."""
        # Liquidity guard: if spread is too wide, abort
        if spread_pct > self.liquidity_guard_spread_pct:
            return RepositionDecision.CANCEL_LIQUIDITY

        # Max reprices reached
        if replace_count >= self.max_reprice_attempts:
            return RepositionDecision.CANCEL

        # If no limit price (market order), no repositioning needed
        if current_limit is None:
            return RepositionDecision.HOLD

        return RepositionDecision.REPOSITION

    def compute_new_price(
        self,
        *,
        side: str,
        current_limit: float | None,
        bid: float,
        ask: float,
        replace_count: int,
    ) -> float:
        """Compute new limit price stepped toward the other side of the spread.

        BUY: step up from bid toward ask (more aggressive)
        SELL: step down from ask toward bid (more aggressive)

        Each step moves `reprice_step_bps` basis points toward crossing.
        Never crosses more than `max_cross_spread_bps` from the starting side.
        """
        mid = (bid + ask) / 2
        step = mid * (self.reprice_step_bps / 10_000)
        max_cross = mid * (self.max_cross_spread_bps / 10_000)

        if side == "buy":
            # Start from current limit or bid, step up by one fixed step
            base = current_limit if current_limit else bid
            new_price = base + step  # Fixed step, not cumulative
            # Cap: don't cross spread more than max_cross from bid
            cap = bid + max_cross
            return round(min(new_price, cap), 8)
        else:
            # Start from current limit or ask, step down by one fixed step
            base = current_limit if current_limit else ask
            new_price = base - step  # Fixed step, not cumulative
            # Floor: don't cross more than max_cross from ask
            floor = ask - max_cross
            return round(max(new_price, floor), 8)
