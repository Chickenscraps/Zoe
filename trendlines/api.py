"""
Public API for the trendlines/levels module.

Downstream strategies (e.g. Bounce Catcher) consume this interface rather
than reaching into internal RANSAC/DBSCAN objects directly.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from trendlines.config import TrendlinesConfig
from trendlines.pivots import (
    Pivot,
    compute_atr,
    detect_pivots_vectorized,
    filter_pivots_by_atr,
)
from trendlines.ransac_fit import FittedLine, fit_trendlines_sequential
from trendlines.dbscan_levels import Level, cluster_levels
from trendlines.scoring import (
    confluence_score_at_price,
    score_level,
    score_trendline,
)
from trendlines.events import StructureEvent, detect_structure_events
from trendlines.persistence import TrendlinePersistence

logger = logging.getLogger(__name__)


class StructureAPI:
    """
    High-level facade consumed by other strategies.

    Typical flow::

        api = StructureAPI(config, db_client)
        api.update(symbol, timeframe, df)        # on candle close
        sup = api.nearest_support("BTC-USD", "1h", 64000)
        res = api.nearest_resistance("BTC-USD", "1h", 64000)
        cscore = api.confluence_score_at("BTC-USD", "1h", 64000)
    """

    def __init__(self, config: TrendlinesConfig, db=None):
        self.cfg = config
        self.persistence = TrendlinePersistence(db) if db else None

        # In-memory cache: { (symbol, tf): { "levels": [...], "trendlines": [...] } }
        self._cache: Dict[tuple, Dict[str, Any]] = {}

    # ── Core update (run on candle close) ────────────────────────────

    def update(self, symbol: str, timeframe: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Full pipeline: pivots → RANSAC → DBSCAN → score → persist → events.

        Parameters
        ----------
        df : DataFrame
            OHLCV candles for the analysis window (oldest first).

        Returns
        -------
        dict with keys: pivots, trendlines, levels, events
        """
        if not self.cfg.enabled:
            return {"pivots": [], "trendlines": [], "levels": [], "events": []}

        cfg = self.cfg
        t0 = time.time()

        # 1. Detect pivots
        pivots = detect_pivots_vectorized(df, k=cfg.pivots.k, sources=cfg.pivots.sources)
        pivots = filter_pivots_by_atr(
            pivots, df,
            atr_len=cfg.pivots.atr_len,
            atr_pivot_mult=cfg.pivots.atr_pivot_mult,
        )
        # Bound by max_pivots (keep most recent)
        if len(pivots) > cfg.pivots.max_pivots:
            pivots = pivots[-cfg.pivots.max_pivots:]

        # 2. Compute median ATR for adaptive params
        atr_array = compute_atr(df, cfg.pivots.atr_len)
        valid_atr = atr_array[~np.isnan(atr_array)]
        median_atr = float(np.median(valid_atr)) if len(valid_atr) > 0 else 0.0
        current_price = float(df["close"].iloc[-1])

        # 3. Fit trendlines (support from lows, resistance from highs)
        pivot_lows = [p for p in pivots if p.type == "low"]
        pivot_highs = [p for p in pivots if p.type == "high"]

        support_lines = fit_trendlines_sequential(
            pivot_lows,
            side="support",
            median_atr=median_atr,
            atr_tol_mult=cfg.tolerance.atr_tol_mult,
            pct_tol=cfg.tolerance.pct_tol,
            min_inliers=cfg.fitting.min_pivots,
            max_lines=cfg.fitting.max_lines_per_side,
            max_trials=cfg.fitting.max_trials,
            random_state=cfg.fitting.random_state,
            reference_price=current_price,
        )
        resistance_lines = fit_trendlines_sequential(
            pivot_highs,
            side="resistance",
            median_atr=median_atr,
            atr_tol_mult=cfg.tolerance.atr_tol_mult,
            pct_tol=cfg.tolerance.pct_tol,
            min_inliers=cfg.fitting.min_pivots,
            max_lines=cfg.fitting.max_lines_per_side,
            max_trials=cfg.fitting.max_trials,
            random_state=cfg.fitting.random_state,
            reference_price=current_price,
        )
        all_lines = support_lines + resistance_lines

        # 4. Cluster horizontal levels
        levels = cluster_levels(
            pivots_high=pivot_highs,
            pivots_low=pivot_lows,
            median_atr=median_atr,
            eps_atr_mult=cfg.horizontals.eps_atr_mult,
            min_samples=cfg.horizontals.min_samples,
            min_cluster_touches=cfg.horizontals.min_cluster_touches,
        )

        # 5. Score everything
        now_ts = datetime.now(timezone.utc).timestamp()
        weights = cfg.scoring.weights

        for line in all_lines:
            line.score = score_trendline(
                line, now_ts, levels=levels, weights=weights,
                current_price=current_price,
            )
        for lv in levels:
            lv.score = score_level(
                lv, now_ts, trendlines=all_lines, weights=weights,
            )

        # Filter low-score levels
        levels = [lv for lv in levels if lv.score >= cfg.scoring.min_score_to_keep]

        # 6. Detect events
        closes = df["close"].tolist()
        events = detect_structure_events(
            symbol, timeframe, closes, all_lines, levels,
            now_ts, config=cfg.events, atr=median_atr,
        )

        # 7. Persist
        if self.persistence:
            self.persistence.upsert_pivots(symbol, timeframe, pivots)
            self.persistence.save_trendlines(symbol, timeframe, all_lines)
            self.persistence.save_levels(symbol, timeframe, levels)
            for ev in events:
                self.persistence.insert_event(ev)

        # 8. Cache
        self._cache[(symbol, timeframe)] = {
            "trendlines": all_lines,
            "levels": levels,
            "median_atr": median_atr,
            "current_price": current_price,
            "updated_at": now_ts,
        }

        elapsed = time.time() - t0
        logger.info(
            "[%s %s] structure update: %d pivots, %d lines, %d levels, "
            "%d events (%.1fms)",
            symbol, timeframe, len(pivots), len(all_lines),
            len(levels), len(events), elapsed * 1000,
        )

        return {
            "pivots": pivots,
            "trendlines": all_lines,
            "levels": levels,
            "events": events,
        }

    # ── Query helpers ────────────────────────────────────────────────

    def get_levels(self, symbol: str, timeframe: str) -> List[Level]:
        cached = self._cache.get((symbol, timeframe))
        return cached["levels"] if cached else []

    def get_trendlines(self, symbol: str, timeframe: str) -> List[FittedLine]:
        cached = self._cache.get((symbol, timeframe))
        return cached["trendlines"] if cached else []

    def nearest_support(self, symbol: str, timeframe: str, price: float) -> Optional[Level]:
        levels = self.get_levels(symbol, timeframe)
        candidates = [lv for lv in levels if lv.role in ("support", "flip") and lv.centroid <= price]
        if not candidates:
            return None
        return max(candidates, key=lambda lv: lv.centroid)

    def nearest_resistance(self, symbol: str, timeframe: str, price: float) -> Optional[Level]:
        levels = self.get_levels(symbol, timeframe)
        candidates = [lv for lv in levels if lv.role in ("resistance", "flip") and lv.centroid >= price]
        if not candidates:
            return None
        return min(candidates, key=lambda lv: lv.centroid)

    def best_support_zone(
        self, symbol: str, timeframe: str, price: float, depth: int = 3
    ) -> List[Level]:
        levels = self.get_levels(symbol, timeframe)
        candidates = [lv for lv in levels if lv.role in ("support", "flip") and lv.centroid <= price]
        candidates.sort(key=lambda lv: lv.score, reverse=True)
        return candidates[:depth]

    def confluence_score_at(
        self, symbol: str, timeframe: str, price: float
    ) -> float:
        cached = self._cache.get((symbol, timeframe))
        if not cached:
            return 0.0
        now_ts = cached.get("updated_at", time.time())
        atr = cached.get("median_atr", 0.0)
        return confluence_score_at_price(
            price, cached["levels"], cached["trendlines"], now_ts, atr,
        )

    def has_active_breakout(self, symbol: str, timeframe: str) -> bool:
        """Check if a breakout event was detected in the most recent update."""
        cached = self._cache.get((symbol, timeframe))
        if not cached:
            return False
        return any(
            e.event_type == "breakout" and e.confirmed
            for e in cached.get("events", [])
        )

    def has_active_retest(self, symbol: str, timeframe: str) -> bool:
        cached = self._cache.get((symbol, timeframe))
        if not cached:
            return False
        return any(
            e.event_type == "retest" and e.confirmed
            for e in cached.get("events", [])
        )

    # ── JSON payload for dashboard ───────────────────────────────────

    def to_json(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Serialise current state for dashboard overlays."""
        cached = self._cache.get((symbol, timeframe))
        if not cached:
            return {"symbol": symbol, "timeframe": timeframe, "levels": [], "trendlines": []}

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "median_atr": cached["median_atr"],
            "current_price": cached["current_price"],
            "updated_at": cached["updated_at"],
            "levels": [
                {
                    "centroid": lv.centroid,
                    "top": lv.top,
                    "bottom": lv.bottom,
                    "role": lv.role,
                    "touch_count": lv.touch_count,
                    "score": lv.score,
                }
                for lv in cached["levels"]
            ],
            "trendlines": [
                {
                    "slope": line.slope,
                    "intercept": line.intercept,
                    "side": line.side,
                    "inlier_count": line.inlier_count,
                    "score": line.score,
                }
                for line in cached["trendlines"]
            ],
        }
