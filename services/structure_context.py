"""
Structure Context — integration layer between Trendlines, Bounce, and the
existing strategy stack.

This service:
  1. Runs the trendlines module on candle close (15m/1h/4h/1d)
  2. Provides structural context to the Bounce Catcher
  3. Implements the "structure gate" (no bounce entries into liquidity holes)
  4. Fuses multi-timeframe structure for downstream consumption

Designed to be instantiated once at bot startup and called per-tick.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from trendlines.api import StructureAPI
from trendlines.config import TrendlinesConfig
from bounce.bounce_catcher import BounceCatcher
from bounce.config import BounceConfig
from bounce.entry_planner import TradeIntent

logger = logging.getLogger(__name__)


class StructureContextService:
    """
    Orchestrates trendlines analysis and bounce detection.

    Example::

        svc = StructureContextService(trend_cfg, bounce_cfg, db_client)
        svc.on_candle_close("BTC-USD", "15m", df_15m, indicators, market_state)
    """

    def __init__(
        self,
        trendlines_config: TrendlinesConfig,
        bounce_config: BounceConfig,
        db=None,
    ):
        self.structure_api = StructureAPI(trendlines_config, db=db)
        self.bounce = BounceCatcher(bounce_config, db=db)
        self.trend_cfg = trendlines_config
        self.bounce_cfg = bounce_config

        # Track last update timestamps per (symbol, tf) to avoid redundant work
        self._last_update: Dict[tuple, float] = {}

    # ── Primary entry point ──────────────────────────────────────────

    def on_candle_close(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        df_1h: Optional[pd.DataFrame] = None,
        indicators: Dict[str, Any] = None,
        market_state: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Called when a candle closes for (symbol, timeframe).

        Returns a dict with structural context and any emitted bounce intent.
        """
        indicators = indicators or {}
        market_state = market_state or {}
        result: Dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "structure_updated": False,
            "bounce_intent": None,
            "events": [],
        }

        # 1. Update structure (trendlines + levels)
        if self.trend_cfg.enabled and timeframe in self.trend_cfg.timeframes:
            structure = self.structure_api.update(symbol, timeframe, df)
            result["structure_updated"] = True
            result["events"] = structure.get("events", [])

        # 2. Run bounce catcher on 15m candles
        if timeframe == "15m" and symbol in self.bounce_cfg.universe:
            intent = self.bounce.process_tick(
                symbol=symbol,
                df_15m=df,
                df_1h=df_1h,
                indicators=indicators,
                market_state=market_state,
                structure_api=self.structure_api,
            )
            result["bounce_intent"] = intent

        return result

    # ── Query helpers (pass through to structure API) ────────────────

    def get_structure_json(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        return self.structure_api.to_json(symbol, timeframe)

    def nearest_support(self, symbol: str, tf: str, price: float):
        return self.structure_api.nearest_support(symbol, tf, price)

    def nearest_resistance(self, symbol: str, tf: str, price: float):
        return self.structure_api.nearest_resistance(symbol, tf, price)

    def confluence_at(self, symbol: str, tf: str, price: float) -> float:
        return self.structure_api.confluence_score_at(symbol, tf, price)

    # ── Startup: restore bounce state ────────────────────────────────

    def restore(self):
        """Restore bounce catcher state from DB on bot startup."""
        for symbol in self.bounce_cfg.universe:
            self.bounce.restore_state(symbol)
            logger.info("[%s] bounce state restored", symbol)
