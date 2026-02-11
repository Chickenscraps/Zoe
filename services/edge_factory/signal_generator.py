from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .config import EdgeFactoryConfig
from .models import EdgePosition, RegimeState, Signal
from .regime_detector import RegimeDetector

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Regime-Adaptive Sniper V1 signal logic.

    Entry Conditions (ALL must be true):
    1. Regime allows trading (low_vol_bull or transition)
    2. trend_z_score_14d > 0.8 (attention spike)
    3. funding_rate_basis < 0.05% (not overheated)
    4. vwap_distance > 0 (price above VWAP)
    5. corwin_schultz_spread < 0.6% (sufficient liquidity)
    6. portfolio_heat < 60% (room for more risk)
    7. consecutive_loss_count < 4 (tilt protection)

    Exit Conditions (ANY triggers):
    - Price >= TP (+4%)
    - Price <= SL (-2%)
    - Position age > 48h
    - Regime changed to high_vol_crash
    """

    def __init__(self, config: EdgeFactoryConfig, regime_detector: RegimeDetector):
        self.config = config
        self.regime = regime_detector

    def evaluate(
        self,
        symbol: str,
        features: dict[str, float],
        regime: RegimeState,
    ) -> Signal | None:
        """
        Evaluate entry conditions for a symbol.
        Returns Signal if all conditions met, None otherwise.
        """
        # Gate 1: Regime
        if not regime.allows_trading():
            logger.debug("%s: Blocked by regime (%s)", symbol, regime.regime)
            return None

        # Gate 2: Trend Z-Score
        trend_z = features.get("trend_z_score_14d")
        if trend_z is None or trend_z < self.config.trend_z_threshold:
            logger.debug("%s: Trend Z too low (%.2f < %.2f)", symbol, trend_z or 0, self.config.trend_z_threshold)
            return None

        # Gate 3: Funding Rate
        funding = features.get("funding_rate_basis")
        if funding is not None and funding > self.config.funding_rate_max:
            logger.debug("%s: Funding rate too high (%.5f > %.5f)", symbol, funding, self.config.funding_rate_max)
            return None

        # Gate 4: VWAP Distance (price above VWAP)
        vwap_dist = features.get("vwap_distance")
        if vwap_dist is not None and vwap_dist <= 0:
            logger.debug("%s: Price below VWAP (%.4f)", symbol, vwap_dist)
            return None

        # Gate 5: Liquidity (Corwin-Schultz spread)
        cs_spread = features.get("corwin_schultz_spread")
        if cs_spread is not None and cs_spread > self.config.corwin_schultz_max:
            logger.debug("%s: Spread too wide (%.4f > %.4f)", symbol, cs_spread, self.config.corwin_schultz_max)
            return None

        # Gate 6: Portfolio Heat
        heat = features.get("portfolio_heat", 0.0)
        if heat >= self.config.portfolio_heat_max:
            logger.debug("%s: Portfolio too hot (%.1f%% >= %.1f%%)", symbol, heat * 100, self.config.portfolio_heat_max * 100)
            return None

        # Gate 7: Consecutive Losses (tilt protection)
        losses = features.get("consecutive_loss_count", 0.0)
        if losses >= self.config.consecutive_loss_max:
            logger.debug("%s: Too many consecutive losses (%d)", symbol, int(losses))
            return None

        # All gates passed — generate signal
        strength = self._compute_strength(features, regime)

        signal = Signal(
            symbol=symbol,
            direction="long",
            strength=strength,
            regime=regime,
            features=features.copy(),
            generated_at=datetime.now(timezone.utc),
            strategy_name="regime_adaptive_sniper",
        )

        logger.info(
            "SIGNAL: %s LONG (strength=%.2f, z=%.2f, funding=%.5f, regime=%s)",
            symbol, strength, trend_z or 0, funding or 0, regime.regime,
        )
        return signal

    def _compute_strength(self, features: dict[str, float], regime: RegimeState) -> float:
        """Weighted signal strength from 0.0-1.0."""
        score = 0.0

        # Trend Z contribution (0-0.3)
        z = features.get("trend_z_score_14d", 0)
        score += min(z / 3.0, 1.0) * 0.3

        # Funding rate contribution (0-0.2) — lower is better
        funding = features.get("funding_rate_basis", 0)
        funding_score = max(0, 1.0 - abs(funding) / 0.001)
        score += funding_score * 0.2

        # VWAP contribution (0-0.15)
        vwap = features.get("vwap_distance", 0)
        score += min(max(vwap, 0) / 0.05, 1.0) * 0.15

        # Efficiency Ratio contribution (0-0.15)
        er = features.get("efficiency_ratio", 0)
        score += min(er, 1.0) * 0.15

        # Regime multiplier (0-0.2)
        score += regime.confidence * 0.2

        return min(max(score, 0.0), 1.0)

    def check_exit(
        self,
        position: EdgePosition,
        current_price: float,
        features: dict[str, float],
        regime: RegimeState,
    ) -> str | None:
        """
        Check exit conditions for an open position.
        Returns exit reason string or None if no exit needed.
        """
        # Take Profit
        if position.check_tp(current_price):
            logger.info(
                "EXIT %s: Take Profit (%.2f >= %.2f)",
                position.symbol, current_price, position.tp_price,
            )
            return "take_profit"

        # Stop Loss
        if position.check_sl(current_price):
            logger.info(
                "EXIT %s: Stop Loss (%.2f <= %.2f)",
                position.symbol, current_price, position.sl_price,
            )
            return "stop_loss"

        # Position Timeout
        now = datetime.now(timezone.utc)
        max_age = timedelta(hours=self.config.position_timeout_hours)
        if now - position.entry_time > max_age:
            logger.info("EXIT %s: Timeout (%dh)", position.symbol, self.config.position_timeout_hours)
            return "timeout"

        # Regime Change to Crash
        if regime.regime == "high_vol_crash":
            logger.info("EXIT %s: Regime crash detected", position.symbol)
            return "regime_change"

        return None
