"""
Tests for breakout / breakdown / retest event detection.
"""

import pytest
from datetime import datetime, timezone

from trendlines.dbscan_levels import Level
from trendlines.ransac_fit import FittedLine
from trendlines.events import detect_structure_events, EventsConfig


class TestBreakoutEvents:
    def test_breakout_above_resistance(self):
        """Two consecutive closes above resistance → confirmed breakout."""
        levels = [
            Level(centroid=100, top=101, bottom=99, role="resistance",
                  touch_count=5),
        ]
        # Two closes above 101 + epsilon
        closes = [99, 100, 100.5, 102, 103]
        now = datetime.now(timezone.utc).timestamp()

        events = detect_structure_events(
            "BTC-USD", "15m", closes, [], levels, now,
            config=EventsConfig(confirm_closes_15m=2),
        )

        breakouts = [e for e in events if e.event_type == "breakout"]
        assert len(breakouts) >= 1
        assert breakouts[0].confirmed is True

    def test_no_breakout_if_insufficient_closes(self):
        """Only one close above → not confirmed yet."""
        levels = [
            Level(centroid=100, top=101, bottom=99, role="resistance",
                  touch_count=5),
        ]
        closes = [99, 100, 100.5, 99.5, 102]  # only last bar above
        now = datetime.now(timezone.utc).timestamp()

        events = detect_structure_events(
            "BTC-USD", "15m", closes, [], levels, now,
            config=EventsConfig(confirm_closes_15m=2),
        )

        breakouts = [e for e in events if e.event_type == "breakout"]
        # May find 0 or a non-confirmed event
        for b in breakouts:
            assert b.confirm_count < 2

    def test_breakdown_below_support(self):
        """Consecutive closes below support → breakdown."""
        levels = [
            Level(centroid=100, top=101, bottom=99, role="support",
                  touch_count=5),
        ]
        closes = [101, 100, 99.5, 97, 96]
        now = datetime.now(timezone.utc).timestamp()

        events = detect_structure_events(
            "BTC-USD", "15m", closes, [], levels, now,
            config=EventsConfig(confirm_closes_15m=2),
        )

        breakdowns = [e for e in events if e.event_type == "breakdown"]
        assert len(breakdowns) >= 1


class TestRetestEvents:
    def test_retest_after_break(self):
        """Price returns to zone after breaking below → retest."""
        levels = [
            Level(centroid=100, top=101, bottom=99, role="support",
                  touch_count=5),
        ]
        # Price was below, then comes back to zone
        closes = [97, 96, 95, 96, 97, 98, 99, 100, 100.5]
        now = datetime.now(timezone.utc).timestamp()

        events = detect_structure_events(
            "BTC-USD", "15m", closes, [], levels, now,
            config=EventsConfig(confirm_closes_15m=2),
            atr=2.0,
        )

        retests = [e for e in events if e.event_type == "retest"]
        assert len(retests) >= 1
