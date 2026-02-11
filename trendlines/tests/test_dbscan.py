"""
Tests for DBSCAN horizontal level clustering.
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from trendlines.pivots import Pivot, detect_pivots_vectorized, compute_atr
from trendlines.dbscan_levels import cluster_levels, Level
from trendlines.tests.fixtures import make_range_bound_df


def _make_manual_pivots(prices, type_="low", source="wick"):
    """Create pivots at specified prices for testing."""
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        Pivot(timestamp=t0 + timedelta(hours=i), price=p, type=type_, source=source)
        for i, p in enumerate(prices)
    ]


class TestDBSCANClustering:
    def test_basic_clustering(self):
        """Two distinct price clusters → two levels."""
        lows = _make_manual_pivots([100, 100.5, 99.8, 101, 200, 200.3, 199.5, 200.8])
        highs = _make_manual_pivots([300, 300.5, 301], type_="high")

        levels = cluster_levels(highs, lows, median_atr=5.0, eps_atr_mult=0.5, min_samples=3)

        # Should find at least the ~100 support cluster and ~300 resistance
        support = [lv for lv in levels if lv.role == "support"]
        assert len(support) >= 1
        # The centroid of the ~100 cluster should be close to 100
        assert any(abs(lv.centroid - 100.3) < 2 for lv in support)

    def test_stable_under_same_atr(self):
        """Same pivots + same ATR → identical clusters (deterministic)."""
        lows = _make_manual_pivots([50, 50.1, 49.9, 50.2, 49.8, 80, 80.1, 79.9])
        highs = _make_manual_pivots([], type_="high")

        run1 = cluster_levels(highs, lows, median_atr=2.0, eps_atr_mult=0.5)
        run2 = cluster_levels(highs, lows, median_atr=2.0, eps_atr_mult=0.5)

        assert len(run1) == len(run2)
        for l1, l2 in zip(run1, run2):
            assert l1.centroid == l2.centroid
            assert l1.touch_count == l2.touch_count

    def test_atr_scaling(self):
        """Higher ATR → wider epsilon → potentially fewer, wider clusters."""
        prices = [100, 100.5, 101, 102, 102.5, 103]
        lows = _make_manual_pivots(prices)
        highs = _make_manual_pivots([], type_="high")

        # Low ATR: points 100-101 and 102-103 might be separate clusters
        tight = cluster_levels(highs, lows, median_atr=1.0, eps_atr_mult=0.5, min_samples=2)
        # High ATR: all 6 points might merge into one cluster
        wide = cluster_levels(highs, lows, median_atr=10.0, eps_atr_mult=0.5, min_samples=2)

        assert len(tight) >= len(wide)

    def test_noise_handling(self):
        """Isolated pivots (noise) are NOT clustered."""
        # 5 points near 100, 1 outlier at 500
        lows = _make_manual_pivots([100, 100.2, 99.8, 100.1, 99.9, 500])
        highs = _make_manual_pivots([], type_="high")

        levels = cluster_levels(highs, lows, median_atr=1.0, eps_atr_mult=0.5, min_samples=3)

        # The 500 outlier should not form a cluster
        centroids = [lv.centroid for lv in levels]
        assert not any(abs(c - 500) < 10 for c in centroids)

    def test_flip_level_detection(self):
        """Overlapping S/R zones → flip level."""
        # Support zone around 100
        lows = _make_manual_pivots([100, 100.1, 99.9, 100.2])
        # Resistance zone around 100.3 (overlapping within ATR)
        highs = _make_manual_pivots([100.3, 100.4, 100.2, 100.5], type_="high")

        levels = cluster_levels(
            highs, lows, median_atr=2.0,
            eps_atr_mult=0.5, min_samples=3,
            flip_overlap_tol_atr=0.5,
        )

        flips = [lv for lv in levels if lv.role == "flip"]
        assert len(flips) >= 1

    def test_min_cluster_touches(self):
        """Clusters with fewer than min_cluster_touches are discarded."""
        lows = _make_manual_pivots([100, 100.1])  # only 2 points
        highs = _make_manual_pivots([], type_="high")

        levels = cluster_levels(
            highs, lows, median_atr=1.0,
            eps_atr_mult=0.5, min_samples=2, min_cluster_touches=3,
        )
        assert len(levels) == 0

    def test_range_bound_fixture(self):
        """Range-bound data produces levels near the top and bottom."""
        df = make_range_bound_df(n=150, center=50000, half_range=500)
        pivots_all = detect_pivots_vectorized(df, k=3, sources=["wick"])
        atr = compute_atr(df, 14)
        med_atr = float(np.nanmedian(atr))

        highs = [p for p in pivots_all if p.type == "high"]
        lows = [p for p in pivots_all if p.type == "low"]

        levels = cluster_levels(highs, lows, median_atr=med_atr)
        assert len(levels) > 0
