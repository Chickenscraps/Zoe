from __future__ import annotations

import logging
from typing import Any

from ..config import EdgeFactoryConfig
from ..repository import FeatureRepository
from .intraday_signal_engine import IntradaySignal
from .limit_chase_policy import LimitChasePolicy
from .regime_manager import IntradayRegime, IntradayRegimeManager
from .risk_overlays import RiskOverlays

logger = logging.getLogger(__name__)


class IntradayExecutionAdapter:
    """
    Converts intraday intents into the existing pipeline.

    signal_intent -> risk overlays -> sizing -> limit chase -> order executor

    Records:
    - Why trade allowed/blocked
    - Regime state
    - Thresholds used
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        repository: FeatureRepository,
        regime_manager: IntradayRegimeManager,
        risk_overlays: RiskOverlays,
        limit_chase: LimitChasePolicy,
    ):
        self.config = config
        self.repo = repository
        self.regime_manager = regime_manager
        self.risk_overlays = risk_overlays
        self.limit_chase = limit_chase

    def prepare_order(
        self,
        signal: IntradaySignal,
        bid_price: float,
        features: dict[str, float],
    ) -> dict[str, Any] | None:
        """
        Prepare an order from an intraday signal.

        Returns order params dict or None if blocked.
        Records decision metadata.
        """
        regime = self.regime_manager.current.regime

        # Run risk overlays
        allowed, reason = self.risk_overlays.check_all(
            signal.symbol, regime, features
        )

        if not allowed:
            logger.info(
                "INTRADAY BLOCKED %s: %s (regime=%s)",
                signal.symbol, reason, regime.value,
            )
            return None

        # Compute size (rung-based for intraday)
        equity = self.config.account_equity
        rung_size = equity * self.config.intraday_rung_pct
        size_usd = min(rung_size, self.config.max_notional_per_trade)

        # TP/SL prices
        tp_price = bid_price * (1.0 + signal.tp_pct)
        sl_price = bid_price * (1.0 - signal.sl_pct)

        # Compute chase schedule
        chase = self.limit_chase.compute_chase_schedule(
            bid_price, signal.strength
        )

        order = {
            "symbol": signal.symbol,
            "side": signal.side,
            "size_usd": round(size_usd, 2),
            "limit_price": chase.initial_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "chase_schedule": chase,
            "strategy": signal.strategy,
            "regime": regime.value,
            "signal_strength": signal.strength,
            "expected_move_pct": signal.expected_move_pct,
            "time_stop_hours": signal.time_stop_hours,
        }

        logger.info(
            "INTRADAY ORDER: %s %s $%.2f @ %.4f (TP=%.4f SL=%.4f, strategy=%s)",
            signal.side.upper(), signal.symbol, size_usd,
            chase.initial_price, tp_price, sl_price, signal.strategy,
        )

        return order
