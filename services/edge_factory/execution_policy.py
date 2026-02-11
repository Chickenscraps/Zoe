from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from .config import EdgeFactoryConfig
from .quote_model import Quote

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Execution urgency levels."""

    PASSIVE = "passive"
    NORMAL = "normal"
    PANIC_EXIT = "panic_exit"


@dataclass
class ExecutionParams:
    """Computed execution parameters for a single order."""

    limit_price: float
    ttl_seconds: int
    max_retries: int
    mode: ExecutionMode


class ExecutionPolicyEngine:
    """
    Computes limit prices and order lifecycle params based on urgency.

    Three modes:
    - PASSIVE: bid + 0 buffer. Patient maker-ish fill. For strong signals + tight spreads.
    - NORMAL: bid + dynamic buffer. Standard marketable limit. For typical entries.
    - PANIC_EXIT: crosses spread aggressively. For SL/kill/regime exits.
    """

    def __init__(self, config: EdgeFactoryConfig):
        self.config = config

    def compute_entry_params(
        self,
        quote: Quote,
        mode: ExecutionMode = ExecutionMode.NORMAL,
    ) -> ExecutionParams:
        """
        Compute entry (buy) order parameters.

        PASSIVE: limit at bid, long TTL, more retries
        NORMAL: limit at bid + dynamic buffer, standard TTL
        """
        if mode == ExecutionMode.PASSIVE:
            return ExecutionParams(
                limit_price=quote.bid,
                ttl_seconds=self.config.passive_ttl_sec,
                max_retries=2,
                mode=ExecutionMode.PASSIVE,
            )

        # NORMAL: dynamic buffer based on spread
        buf_pct = max(self.config.min_buf_pct, 0.5 * quote.spread_pct)
        buf_pct = min(buf_pct, self.config.max_buf_pct)
        limit_price = quote.bid * (1.0 + buf_pct)

        return ExecutionParams(
            limit_price=limit_price,
            ttl_seconds=self.config.normal_ttl_sec,
            max_retries=1,
            mode=ExecutionMode.NORMAL,
        )

    def compute_exit_params(
        self,
        quote: Quote,
        reason: str,
    ) -> ExecutionParams:
        """
        Compute exit (sell) order parameters.

        TP/timeout: NORMAL sell at bid - small buffer
        SL/kill/regime: PANIC_EXIT sell crossing spread aggressively
        """
        panic_reasons = {"stop_loss", "kill_switch", "regime_change"}

        if reason in panic_reasons:
            # Aggressive: willing to sell at bid - full spread buffer
            buf_pct = max(self.config.min_buf_pct, quote.spread_pct)
            buf_pct = min(buf_pct, 0.005)  # Cap at 0.5% to avoid huge give-up
            limit_price = quote.bid * (1.0 - buf_pct)

            return ExecutionParams(
                limit_price=limit_price,
                ttl_seconds=self.config.panic_ttl_sec,
                max_retries=0,
                mode=ExecutionMode.PANIC_EXIT,
            )

        # Normal exit: sell at bid - small buffer
        buf_pct = self.config.min_buf_pct
        limit_price = quote.bid * (1.0 - buf_pct)

        return ExecutionParams(
            limit_price=limit_price,
            ttl_seconds=self.config.normal_ttl_sec,
            max_retries=1,
            mode=ExecutionMode.NORMAL,
        )

    def choose_entry_mode(self, signal_strength: float, spread_pct: float) -> ExecutionMode:
        """
        Decide entry mode based on signal strength and spread.

        PASSIVE: strong signal (>0.7) and tight spread (<0.3%)
        NORMAL: everything else
        """
        if signal_strength > 0.7 and spread_pct < 0.003:
            return ExecutionMode.PASSIVE
        return ExecutionMode.NORMAL
