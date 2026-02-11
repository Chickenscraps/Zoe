"""
Tests for trendline and level scoring.
"""

import pytest
from datetime import datetime, timezone, timedelta

from trendlines.config import ScoringWeights
from trendlines.ransac_fit import FittedLine
from trendlines.dbscan_levels import Level
from trendlines.scoring import score_trendline, score_level, confluence_score_at_price


class TestTrendlineScoring:
    def test_more_touches_higher_score(self):
        """Monotonicity: more inlier touches → higher score."""
        now = datetime.now(timezone.utc).timestamp()
        end = datetime.now(timezone.utc)

        line_3 = FittedLine(slope=0.001, intercept=100, side="support",
                            inlier_count=3, end_at=end)
        line_8 = FittedLine(slope=0.001, intercept=100, side="support",
                            inlier_count=8, end_at=end)

        s3 = score_trendline(line_3, now)
        s8 = score_trendline(line_8, now)
        assert s8 > s3

    def test_recent_line_scores_higher(self):
        """A recently touched line scores higher than an old one."""
        now = datetime.now(timezone.utc).timestamp()

        recent = FittedLine(slope=0.001, intercept=100, side="support",
                            inlier_count=5,
                            end_at=datetime.now(timezone.utc))
        old = FittedLine(slope=0.001, intercept=100, side="support",
                         inlier_count=5,
                         end_at=datetime.now(timezone.utc) - timedelta(days=30))

        s_recent = score_trendline(recent, now)
        s_old = score_trendline(old, now)
        assert s_recent > s_old

    def test_score_range_0_to_100(self):
        """Score is always in [0, 100]."""
        now = datetime.now(timezone.utc).timestamp()
        line = FittedLine(slope=0.001, intercept=100, side="support",
                          inlier_count=50, end_at=datetime.now(timezone.utc))
        s = score_trendline(line, now)
        assert 0 <= s <= 100


class TestLevelScoring:
    def test_flip_level_bonus(self):
        """Flip levels receive a confluence bonus."""
        now = datetime.now(timezone.utc).timestamp()

        support = Level(centroid=100, top=101, bottom=99, role="support",
                        touch_count=5, last_tested=datetime.now(timezone.utc))
        flip = Level(centroid=100, top=101, bottom=99, role="flip",
                     touch_count=5, last_tested=datetime.now(timezone.utc))

        s_support = score_level(support, now)
        s_flip = score_level(flip, now)
        assert s_flip >= s_support

    def test_score_range_0_to_100(self):
        now = datetime.now(timezone.utc).timestamp()
        lv = Level(centroid=100, top=101, bottom=99, role="support",
                   touch_count=20, last_tested=datetime.now(timezone.utc))
        s = score_level(lv, now)
        assert 0 <= s <= 100


class TestConfluenceScore:
    def test_price_inside_level_zone(self):
        """Price inside a level zone → positive confluence."""
        now = datetime.now(timezone.utc).timestamp()
        levels = [Level(centroid=100, top=101, bottom=99, role="support", touch_count=5)]

        cs = confluence_score_at_price(100.5, levels, [], now, atr=2.0)
        assert cs > 0

    def test_price_far_from_structure(self):
        """Price far from any structure → zero confluence."""
        now = datetime.now(timezone.utc).timestamp()
        levels = [Level(centroid=100, top=101, bottom=99, role="support", touch_count=5)]

        cs = confluence_score_at_price(200, levels, [], now, atr=2.0)
        assert cs == 0
