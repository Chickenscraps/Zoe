from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..config import EdgeFactoryConfig

logger = logging.getLogger(__name__)


@dataclass
class ChaseSchedule:
    """A sequence of limit price steps for chasing a fill."""

    initial_price: float
    steps: list[float] = field(default_factory=list)
    interval_seconds: int = 60
    max_price: float = 0.0

    def price_at_step(self, step: int) -> float:
        """Get the limit price at a given step (0-indexed)."""
        if step < 0:
            return self.initial_price
        if step >= len(self.steps):
            return self.steps[-1] if self.steps else self.initial_price
        return self.steps[step]


class LimitChasePolicy:
    """
    Limit chase from research spec.

    If signal strength >= threshold:
    - Place at bid (or bid + 0.05%)
    - Chase up to 3 steps: step_pct per step_interval
    - Never exceed max_cross_pct, never default to market order

    Integrates with the existing ExecutionPolicyEngine as a pricing overlay.
    """

    def __init__(self, config: EdgeFactoryConfig):
        self.config = config

    def compute_chase_schedule(
        self,
        bid_price: float,
        signal_strength: float,
    ) -> ChaseSchedule:
        """
        Compute a chase schedule from bid price.

        Returns a ChaseSchedule with stepped prices.
        For weak signals (< 0.5), returns just the bid with no chase.
        """
        step_pct = self.config.intraday_chase_step_pct
        num_steps = self.config.intraday_chase_steps
        max_cross = self.config.intraday_max_cross_pct
        interval = self.config.intraday_chase_interval_sec

        # Weak signals: just bid, no chase
        if signal_strength < 0.5:
            return ChaseSchedule(
                initial_price=bid_price,
                steps=[],
                interval_seconds=interval,
                max_price=bid_price,
            )

        # Compute step prices
        max_limit = bid_price * (1.0 + max_cross)
        steps = []

        for i in range(num_steps):
            step_price = bid_price * (1.0 + step_pct * (i + 1))
            step_price = min(step_price, max_limit)
            steps.append(round(step_price, 8))

        return ChaseSchedule(
            initial_price=bid_price,
            steps=steps,
            interval_seconds=interval,
            max_price=max_limit,
        )

    def should_chase(self, signal_strength: float) -> bool:
        """Whether this signal strength warrants chasing."""
        return signal_strength >= 0.5
