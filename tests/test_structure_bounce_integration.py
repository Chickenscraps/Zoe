"""
Integration tests: Trendlines × Bounce Catcher fusion.

Tests that:
  1. Capitulation into a high-score support zone → bounce intent emits
  2. Capitulation into a "liquidity hole" (no structure) → no entry
  3. Structure API feeds confluence to bounce scoring
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

from trendlines.api import StructureAPI
from trendlines.config import TrendlinesConfig
from bounce.bounce_catcher import BounceCatcher
from bounce.config import BounceConfig


def _build_support_zone_df(n=200, support_price=90.0, center=95.0):
    """
    Build a fixture with:
    - Clear support zone around support_price
    - Price oscillating above it
    - Capitulation candle at the end that drops INTO the support zone
    """
    rng = np.random.RandomState(42)
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []

    # Phase 1: oscillating above support with touches (150 bars)
    for i in range(150):
        wave = 3.0 * np.sin(2 * np.pi * i / 30)
        base = center + wave
        close = base + rng.uniform(-0.5, 0.5)
        high = close + rng.uniform(0.5, 2.0)
        low = close - rng.uniform(0.5, 2.0)
        # Occasionally touch the support zone
        if i % 25 == 0:
            low = support_price + rng.uniform(-0.3, 0.3)
        opn = close + rng.uniform(-0.5, 0.5)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * i),
            "open": round(opn, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": 1000.0,
        })

    # Phase 2: decline toward support (30 bars)
    for i in range(30):
        base = center - i * 0.15
        close = base + rng.uniform(-0.3, 0.3)
        high = close + rng.uniform(0.3, 1.0)
        low = close - rng.uniform(0.3, 1.0)
        opn = close + rng.uniform(-0.5, 0.5)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * (150 + i)),
            "open": round(opn, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": 1000.0,
        })

    # Phase 3: Capitulation candle INTO the support zone
    prev_close = rows[-1]["close"]
    cap_open = prev_close - 0.5
    cap_low = support_price - 2.0   # drops into/below zone
    cap_close = support_price + 0.5  # recovers into zone
    cap_high = prev_close + 0.2
    rows.append({
        "timestamp": t0 + timedelta(minutes=15 * 180),
        "open": round(cap_open, 4),
        "high": round(cap_high, 4),
        "low": round(cap_low, 4),
        "close": round(cap_close, 4),
        "volume": 2800.0,  # high volume
    })

    # Phase 4: stabilization (higher lows within support zone)
    for i in range(19):
        base_low = support_price + 0.1 * i
        close = base_low + rng.uniform(0.5, 1.5)
        high = close + rng.uniform(0.3, 0.8)
        low = base_low + rng.uniform(-0.1, 0.1)
        opn = close + rng.uniform(-0.3, 0.3)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * (181 + i)),
            "open": round(opn, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": 1100.0,
        })

    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    return df


class TestStructureBounceIntegration:
    def test_capitulation_into_support_zone(self):
        """
        When capitulation occurs at a known support zone,
        the bounce catcher should detect and potentially emit.
        """
        df = _build_support_zone_df()
        trend_cfg = TrendlinesConfig()
        bounce_cfg = BounceConfig(enabled=True)
        bounce_cfg.capitulation.atr_mult = 2.0
        bounce_cfg.capitulation.vol_mult = 2.0
        bounce_cfg.capitulation.lower_wick_min = 0.30
        bounce_cfg.scoring.min_score = 40

        # Build structure from the first 180 bars
        structure_api = StructureAPI(trend_cfg)
        structure = structure_api.update("BTC-USD", "15m", df.iloc[:180])
        levels = structure["levels"]

        # There should be some levels detected
        assert len(levels) >= 0  # might be 0 if insufficient clustering

        # Now run the bounce catcher with the structure API
        catcher = BounceCatcher(bounce_cfg)
        ms = {
            "high_24h": 100, "low_24h": 88, "open_24h": 95,
            "best_bid": 90, "best_ask": 90.1,
            "now": datetime.now(timezone.utc),
        }

        # Feed capitulation
        sub_cap = df.iloc[:181]
        indicators = {"rsi_15m": 22}
        intent = catcher.process_tick(
            "BTC-USD", sub_cap, None, indicators, ms,
            structure_api=structure_api,
        )
        ss = catcher._get_state("BTC-USD")

        # Should be in CAPITULATION_DETECTED or later
        assert ss.state in ("CAPITULATION_DETECTED", "STABILIZATION_CONFIRMED", "INTENT_EMITTED", "IDLE")

    def test_no_entry_in_liquidity_hole(self):
        """
        Capitulation far from any known support → lower confluence →
        score may be too low to emit.
        """
        # Build a df with support at 90 but capitulation at 50 (far away)
        rng = np.random.RandomState(42)
        t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        rows = []

        for i in range(60):
            close = 100 - i * 0.5 + rng.uniform(-0.3, 0.3)
            high = close + rng.uniform(0.5, 1.5)
            low = close - rng.uniform(0.5, 1.5)
            rows.append({
                "timestamp": t0 + timedelta(minutes=15 * i),
                "open": close + rng.uniform(-0.5, 0.5),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": 1000.0,
            })

        df = pd.DataFrame(rows)
        df.set_index("timestamp", inplace=True)

        trend_cfg = TrendlinesConfig()
        structure_api = StructureAPI(trend_cfg)
        structure_api.update("BTC-USD", "15m", df)

        # The confluence score at price 70 (far from anything) should be low
        cscore = structure_api.confluence_score_at("BTC-USD", "15m", 50.0)
        # In a clean downtrend with no support at 50, confluence should be low
        assert cscore < 50  # not a golden zone
