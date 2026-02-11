from __future__ import annotations

import logging
from datetime import datetime, timezone

from .config import EdgeFactoryConfig
from .models import RegimeState
from .repository import FeatureRepository

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Market regime classifier for crypto markets.

    V1: Simplified state machine using ADX, volatility, and drawdown.

    States:
    - "low_vol_bull":    ADX indicates trend, direction bullish, vol moderate → ACTIVE
    - "high_vol_crash":  Vol extreme OR drawdown severe → HALT
    - "transition":      Everything else → CAUTIOUS (50% sizing)

    V2 (future): Replace with proper HMM using hmmlearn library on daily BTC returns.
    """

    def __init__(self, config: EdgeFactoryConfig, repository: FeatureRepository):
        self.config = config
        self.repo = repository

    def detect(self, features: dict[str, float]) -> RegimeState:
        """
        Classify current regime from latest feature values.

        Required features (will use defaults if missing):
        - garman_klass_vol
        - adx_trend_strength
        - drawdown_current
        - vwap_distance (for direction)
        """
        vol = features.get("garman_klass_vol", 0.5)
        adx = features.get("adx_trend_strength", 0.3)
        drawdown = features.get("drawdown_current", 0.0)
        vwap_dist = features.get("vwap_distance", 0.0)
        rsi_state = features.get("rsi_regime_state", 0.5)
        efficiency = features.get("efficiency_ratio", 0.3)
        amihud_z = features.get("amihud_spike_z", 0.0)

        features_used = {
            "garman_klass_vol": vol,
            "adx_trend_strength": adx,
            "drawdown_current": drawdown,
            "vwap_distance": vwap_dist,
            "rsi_regime_state": rsi_state,
            "amihud_spike_z": amihud_z,
        }

        now = datetime.now(timezone.utc)

        # ── HIGH_VOL_CRASH detection ────────────────────────
        # Annualized vol > 100% OR drawdown > kill switch threshold
        # OR Amihud spike z > 2.0 (liquidity hole)
        if vol > 1.0 or drawdown > self.config.max_drawdown_24h_pct or amihud_z > 2.0:
            regime = RegimeState(
                regime="high_vol_crash",
                confidence=min(0.5 + vol * 0.3 + drawdown * 2, 1.0),
                detected_at=now,
                features_used=features_used,
            )
            logger.info(
                "Regime: HIGH_VOL_CRASH (vol=%.2f, dd=%.2f%%, amihud_z=%.2f)",
                vol, drawdown * 100, amihud_z,
            )
            return regime

        # ── LOW_VOL_BULL detection ──────────────────────────
        # ADX showing trend (normalized > 0.3), price above VWAP, vol reasonable
        is_trending = adx > 0.3
        is_bullish = vwap_dist > 0
        vol_acceptable = vol < 0.80  # < 80% annualized

        if is_trending and is_bullish and vol_acceptable:
            confidence = min(
                0.4
                + (adx * 0.3)          # Higher ADX = more confident
                + (0.2 if vwap_dist > 0.01 else 0.1)  # Stronger above VWAP
                + (0.1 if efficiency > 0.3 else 0),     # Clean trend
                1.0,
            )
            regime = RegimeState(
                regime="low_vol_bull",
                confidence=confidence,
                detected_at=now,
                features_used=features_used,
            )
            logger.info(
                "Regime: LOW_VOL_BULL (adx=%.2f, vwap=%.3f%%, vol=%.2f)",
                adx, vwap_dist * 100, vol,
            )
            return regime

        # ── TRANSITION (default) ────────────────────────────
        confidence = 0.3 + (0.1 if adx > 0.2 else 0) + (0.1 if vol < 0.6 else 0)
        regime = RegimeState(
            regime="transition",
            confidence=min(confidence, 1.0),
            detected_at=now,
            features_used=features_used,
        )
        logger.info("Regime: TRANSITION (adx=%.2f, vol=%.2f)", adx, vol)
        return regime

    def should_trade(self, regime: RegimeState) -> bool:
        """Returns True if regime allows new position entries."""
        return regime.allows_trading()

    def persist(self, regime: RegimeState) -> str:
        """Store regime in repository and return ID."""
        return self.repo.insert_regime(regime)
