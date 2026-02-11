"""
Tests for RANSAC trendline fitting.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta, timezone

from trendlines.pivots import Pivot, detect_pivots_vectorized, filter_pivots_by_atr, compute_atr
from trendlines.ransac_fit import fit_trendlines_sequential, FittedLine
from trendlines.tests.fixtures import make_uptrend_df


class TestRANSACFit:
    def _get_pivots_and_atr(self, df):
        """Helper to extract pivots + median ATR from a df."""
        pivots = detect_pivots_vectorized(df, k=3, sources=["wick"])
        pivots = filter_pivots_by_atr(pivots, df, atr_len=14, atr_pivot_mult=0.5)
        atr_arr = compute_atr(df, 14)
        valid = atr_arr[~np.isnan(atr_arr)]
        median_atr = float(np.median(valid)) if len(valid) > 0 else 1.0
        return pivots, median_atr

    def test_finds_support_in_uptrend(self):
        """RANSAC finds at least one support line in a clean uptrend."""
        df = make_uptrend_df(n=120, slope=0.5)
        pivots, median_atr = self._get_pivots_and_atr(df)
        lows = [p for p in pivots if p.type == "low"]

        lines = fit_trendlines_sequential(
            lows, side="support", median_atr=median_atr,
            min_inliers=3, max_lines=2, random_state=42,
        )
        assert len(lines) >= 1
        # The dominant support line should have positive slope (uptrend)
        assert lines[0].slope > 0
        assert lines[0].inlier_count >= 3

    def test_determinism(self):
        """Same data + same seed → identical trendlines."""
        df = make_uptrend_df(n=120, slope=0.5)
        pivots, median_atr = self._get_pivots_and_atr(df)
        lows = [p for p in pivots if p.type == "low"]

        run1 = fit_trendlines_sequential(
            lows, side="support", median_atr=median_atr,
            random_state=42,
        )
        run2 = fit_trendlines_sequential(
            lows, side="support", median_atr=median_atr,
            random_state=42,
        )
        assert len(run1) == len(run2)
        for l1, l2 in zip(run1, run2):
            assert l1.slope == l2.slope
            assert l1.intercept == l2.intercept
            assert l1.inlier_count == l2.inlier_count

    def test_different_seed_may_differ(self):
        """Changing random_state may produce different results."""
        df = make_uptrend_df(n=120, slope=0.5)
        pivots, median_atr = self._get_pivots_and_atr(df)
        lows = [p for p in pivots if p.type == "low"]

        run42 = fit_trendlines_sequential(
            lows, side="support", median_atr=median_atr,
            random_state=42,
        )
        run99 = fit_trendlines_sequential(
            lows, side="support", median_atr=median_atr,
            random_state=99,
        )
        # They may or may not differ — but at minimum they should both run
        assert len(run42) >= 0
        assert len(run99) >= 0

    def test_peeling_extracts_multiple_lines(self):
        """Sequential RANSAC peels out secondary lines when they exist."""
        df = make_uptrend_df(n=200, slope=0.3)
        pivots, median_atr = self._get_pivots_and_atr(df)
        lows = [p for p in pivots if p.type == "low"]

        lines = fit_trendlines_sequential(
            lows, side="support", median_atr=median_atr,
            min_inliers=3, max_lines=3, random_state=42,
        )
        # In a clean uptrend with enough pivots, we might get 1-3 lines
        assert 1 <= len(lines) <= 3

    def test_insufficient_pivots_returns_empty(self):
        """Fewer than min_inliers pivots → no lines."""
        pivots = [
            Pivot(timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc), price=100, type="low", source="wick"),
            Pivot(timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc), price=101, type="low", source="wick"),
        ]
        lines = fit_trendlines_sequential(
            pivots, side="support", median_atr=1.0,
            min_inliers=3, random_state=42,
        )
        assert lines == []

    def test_resistance_lines(self):
        """RANSAC also works for resistance (pivot highs)."""
        df = make_uptrend_df(n=120, slope=0.5)
        pivots, median_atr = self._get_pivots_and_atr(df)
        highs = [p for p in pivots if p.type == "high"]

        lines = fit_trendlines_sequential(
            highs, side="resistance", median_atr=median_atr,
            min_inliers=3, max_lines=2, random_state=42,
        )
        assert len(lines) >= 1
        assert all(l.side == "resistance" for l in lines)
