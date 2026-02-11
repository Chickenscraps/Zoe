"""
Scoring engine for trendlines and horizontal levels.

Produces a 0-100 "Zoe Score" using weighted components:
  touches, recency decay, confluence, and stability.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

from trendlines.config import ScoringWeights
from trendlines.ransac_fit import FittedLine
from trendlines.dbscan_levels import Level


def score_trendline(
    line: FittedLine,
    now_ts: float,
    levels: Optional[List[Level]] = None,
    weights: Optional[ScoringWeights] = None,
    current_price: float = 0.0,
) -> float:
    """
    Score a RANSAC trendline on [0, 100].

    Components
    ----------
    touches : normalised inlier count (saturates at 10)
    recency : hyperbolic decay from last inlier
    confluence : trendline intersects a horizontal level "near now"
    stability : low residual variance (placeholder; uses inlier count proxy)
    """
    w = weights or ScoringWeights()
    comps: Dict[str, float] = {}

    # 1. Touches (max 100 when inlier_count >= 10)
    touches_raw = min(line.inlier_count / 10.0, 1.0) * 100
    comps["touches"] = touches_raw

    # 2. Recency decay: 100 / (1 + days_since_last_touch)
    if line.end_at:
        seconds_since = max(now_ts - line.end_at.timestamp(), 0)
        days_since = seconds_since / 86400
    else:
        days_since = 999
    recency_raw = 100.0 / (1.0 + days_since)
    comps["recency"] = recency_raw

    # 3. Confluence: does the trendline intersect any level zone at current time?
    confluence_raw = 0.0
    if levels and current_price > 0:
        line_price_now = line.slope * now_ts + line.intercept
        for lv in levels:
            if lv.bottom <= line_price_now <= lv.top:
                confluence_raw = 100.0
                break
            # Near-miss: within 0.5% of zone
            mid = (lv.top + lv.bottom) / 2.0
            if mid > 0 and abs(line_price_now - mid) / mid < 0.005:
                confluence_raw = max(confluence_raw, 60.0)
    comps["confluence"] = confluence_raw

    # 4. Stability proxy: more inliers + narrow time range = more stable
    stability_raw = min(line.inlier_count / 8.0, 1.0) * 100
    comps["stability"] = stability_raw

    score = (
        w.touches * comps["touches"]
        + w.recency * comps["recency"]
        + w.confluence * comps["confluence"]
        + w.stability * comps["stability"]
    )
    return min(max(round(score, 2), 0), 100)


def score_level(
    level: Level,
    now_ts: float,
    trendlines: Optional[List[FittedLine]] = None,
    weights: Optional[ScoringWeights] = None,
) -> float:
    """
    Score a horizontal level on [0, 100].
    """
    w = weights or ScoringWeights()
    comps: Dict[str, float] = {}

    # 1. Touches
    touches_raw = min(level.touch_count / 10.0, 1.0) * 100
    comps["touches"] = touches_raw

    # 2. Recency
    if level.last_tested:
        seconds_since = max(now_ts - level.last_tested.timestamp(), 0)
        days_since = seconds_since / 86400
    else:
        days_since = 999
    recency_raw = 100.0 / (1.0 + days_since)
    comps["recency"] = recency_raw

    # 3. Confluence: trendline passes through the level zone now
    confluence_raw = 0.0
    if trendlines:
        for line in trendlines:
            line_price_now = line.slope * now_ts + line.intercept
            if level.bottom <= line_price_now <= level.top:
                confluence_raw = 100.0
                break
    # Flip levels get bonus
    if level.role == "flip":
        confluence_raw = min(confluence_raw + 30, 100)
    comps["confluence"] = confluence_raw

    # 4. Stability (zone tightness relative to centroid)
    if level.centroid > 0:
        zone_width_pct = (level.top - level.bottom) / level.centroid
        stability_raw = max(0, 100 - zone_width_pct * 5000)
    else:
        stability_raw = 50
    comps["stability"] = stability_raw

    score = (
        w.touches * comps["touches"]
        + w.recency * comps["recency"]
        + w.confluence * comps["confluence"]
        + w.stability * comps["stability"]
    )
    return min(max(round(score, 2), 0), 100)


def confluence_score_at_price(
    price: float,
    levels: List[Level],
    trendlines: List[FittedLine],
    now_ts: float,
    atr: float = 0.0,
) -> float:
    """
    Return a 0-100 "confluence score" indicating how much structural
    support/resistance converges at *price* right now.
    """
    score = 0.0

    for lv in levels:
        if lv.bottom <= price <= lv.top:
            score += 30
            if lv.role == "flip":
                score += 15
            break
        elif atr > 0:
            dist = min(abs(price - lv.top), abs(price - lv.bottom))
            if dist < atr * 0.5:
                score += 15
                break

    for line in trendlines:
        line_price = line.slope * now_ts + line.intercept
        if atr > 0:
            if abs(price - line_price) < atr * 0.35:
                score += 25
                break
        else:
            if abs(price - line_price) / max(price, 1) < 0.003:
                score += 25
                break

    return min(score, 100)
