"""
Tests for pivot detection.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

from trendlines.pivots import detect_pivots_vectorized, filter_pivots_by_atr
from trendlines.tests.fixtures import make_uptrend_df, make_range_bound_df


class TestDetectPivotsVectorized:
    def test_basic_detection(self):
        """Pivots are detected in a simple uptrend."""
        df = make_uptrend_df(n=80)
        pivots = detect_pivots_vectorized(df, k=3, sources=["wick"])

        assert len(pivots) > 0
        highs = [p for p in pivots if p.type == "high"]
        lows = [p for p in pivots if p.type == "low"]
        assert len(highs) > 0
        assert len(lows) > 0

    def test_wick_vs_body_sources(self):
        """Wick and body pivots are separate sets."""
        df = make_uptrend_df(n=80)
        wick_pivots = detect_pivots_vectorized(df, k=3, sources=["wick"])
        body_pivots = detect_pivots_vectorized(df, k=3, sources=["body"])

        assert all(p.source == "wick" for p in wick_pivots)
        assert all(p.source == "body" for p in body_pivots)

    def test_both_sources(self):
        """Requesting both sources returns both."""
        df = make_uptrend_df(n=80)
        both = detect_pivots_vectorized(df, k=3, sources=["wick", "body"])
        wick_only = [p for p in both if p.source == "wick"]
        body_only = [p for p in both if p.source == "body"]
        assert len(wick_only) > 0
        assert len(body_only) > 0

    def test_determinism(self):
        """Same input → identical output."""
        df = make_uptrend_df(n=80)
        run1 = detect_pivots_vectorized(df, k=3)
        run2 = detect_pivots_vectorized(df, k=3)

        assert len(run1) == len(run2)
        for p1, p2 in zip(run1, run2):
            assert p1.timestamp == p2.timestamp
            assert p1.price == p2.price
            assert p1.type == p2.type

    def test_no_pivots_too_short(self):
        """DataFrame shorter than window → empty list."""
        df = make_uptrend_df(n=4)
        pivots = detect_pivots_vectorized(df, k=3)
        assert pivots == []

    def test_confirmation_lag(self):
        """No pivots in the last k bars (not yet confirmed)."""
        df = make_uptrend_df(n=80)
        pivots = detect_pivots_vectorized(df, k=3)
        last_ts = df.index[-3]  # k=3 → last 3 bars are unconfirmed
        for p in pivots:
            assert p.timestamp <= last_ts

    def test_larger_k_fewer_pivots(self):
        """Larger window → fewer, more significant pivots."""
        df = make_uptrend_df(n=200)
        k3 = detect_pivots_vectorized(df, k=3)
        k5 = detect_pivots_vectorized(df, k=5)
        assert len(k3) >= len(k5)


class TestFilterPivotsByATR:
    def test_filter_removes_tiny_pivots(self):
        """ATR filter discards pivots with small excursion."""
        df = make_uptrend_df(n=80)
        pivots = detect_pivots_vectorized(df, k=3)
        filtered = filter_pivots_by_atr(pivots, df, atr_len=14, atr_pivot_mult=0.75)

        assert len(filtered) <= len(pivots)

    def test_atr_snapshot_populated(self):
        """Surviving pivots have atr_snapshot set."""
        df = make_uptrend_df(n=80)
        pivots = detect_pivots_vectorized(df, k=3)
        filtered = filter_pivots_by_atr(pivots, df, atr_len=14, atr_pivot_mult=0.5)

        for p in filtered:
            if p.idx is not None and p.idx >= 14:
                assert p.atr_snapshot is not None
                assert p.atr_snapshot > 0

    def test_zero_mult_keeps_all(self):
        """atr_pivot_mult=0 keeps everything."""
        df = make_uptrend_df(n=80)
        pivots = detect_pivots_vectorized(df, k=3)
        filtered = filter_pivots_by_atr(pivots, df, atr_len=14, atr_pivot_mult=0.0)
        assert len(filtered) == len(pivots)
