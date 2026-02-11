"""
Horizontal level clustering via DBSCAN.

Discovers support/resistance zones from pivot prices without requiring a
pre-specified number of clusters.  Uses ATR-adaptive epsilon so the
algorithm auto-calibrates across assets and volatility regimes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
from sklearn.cluster import DBSCAN

from trendlines.pivots import Pivot


@dataclass
class Level:
    """A horizontal support/resistance zone derived from DBSCAN."""
    centroid: float
    top: float
    bottom: float
    role: str                  # 'support' | 'resistance' | 'flip'
    touch_count: int
    pivots: List[Pivot] = field(default_factory=list)
    first_tested: Optional[datetime] = None
    last_tested: Optional[datetime] = None
    score: float = 0.0
    metadata: Dict = field(default_factory=dict)


def cluster_levels(
    pivots_high: List[Pivot],
    pivots_low: List[Pivot],
    median_atr: float,
    *,
    eps_atr_mult: float = 0.25,
    min_samples: int = 3,
    min_cluster_touches: int = 3,
    flip_overlap_tol_atr: float = 0.5,
) -> List[Level]:
    """
    Cluster pivot prices into horizontal S/R zones.

    Parameters
    ----------
    pivots_high : list[Pivot]
        Pivot highs (candidates for resistance zones).
    pivots_low : list[Pivot]
        Pivot lows (candidates for support zones).
    median_atr : float
        Median ATR — drives ``eps = median_atr * eps_atr_mult``.
    eps_atr_mult : float
        Multiplier for DBSCAN epsilon.
    min_samples : int
        DBSCAN ``min_samples`` (density threshold).
    min_cluster_touches : int
        Clusters with fewer points are discarded.
    flip_overlap_tol_atr : float
        If a resistance zone centroid is within ``flip_overlap_tol_atr * ATR``
        of a support zone centroid, merge them into a *flip* level.

    Returns
    -------
    list[Level]
        Discovered levels sorted by centroid price.
    """
    eps = max(median_atr * eps_atr_mult, 1e-8)  # guard against zero-ATR

    resistance_zones = _cluster_side(pivots_high, eps, min_samples, min_cluster_touches, role="resistance")
    support_zones = _cluster_side(pivots_low, eps, min_samples, min_cluster_touches, role="support")

    # Detect flip levels (overlapping S/R)
    flip_tol = median_atr * flip_overlap_tol_atr if median_atr > 0 else eps
    merged = _merge_flip_levels(support_zones, resistance_zones, flip_tol)

    merged.sort(key=lambda lv: lv.centroid)
    return merged


# ── internal ─────────────────────────────────────────────────────────────

def _cluster_side(
    pivots: List[Pivot],
    eps: float,
    min_samples: int,
    min_cluster_touches: int,
    role: str,
) -> List[Level]:
    if len(pivots) < min_samples:
        return []

    prices = np.array([p.price for p in pivots]).reshape(-1, 1)

    db = DBSCAN(eps=eps, min_samples=min_samples).fit(prices)
    labels = db.labels_

    levels: List[Level] = []
    unique_labels = set(labels)
    unique_labels.discard(-1)  # noise

    for label in sorted(unique_labels):
        mask = labels == label
        cluster_pivots = [pivots[i] for i in range(len(pivots)) if mask[i]]
        cluster_prices = prices[mask].flatten()

        if len(cluster_pivots) < min_cluster_touches:
            continue

        centroid = float(cluster_prices.mean())
        top = float(cluster_prices.max())
        bottom = float(cluster_prices.min())

        ts_list = [p.timestamp for p in cluster_pivots]
        first = min(ts_list)
        last = max(ts_list)

        levels.append(Level(
            centroid=centroid,
            top=top,
            bottom=bottom,
            role=role,
            touch_count=len(cluster_pivots),
            pivots=cluster_pivots,
            first_tested=first,
            last_tested=last,
        ))

    return levels


def _merge_flip_levels(
    support_zones: List[Level],
    resistance_zones: List[Level],
    tol: float,
) -> List[Level]:
    """Merge overlapping S/R into flip levels; leave non-overlapping as-is."""
    merged: List[Level] = []
    used_r: set = set()

    for s in support_zones:
        best_r_idx = None
        best_dist = float("inf")
        for i, r in enumerate(resistance_zones):
            if i in used_r:
                continue
            dist = abs(s.centroid - r.centroid)
            if dist < tol and dist < best_dist:
                best_dist = dist
                best_r_idx = i

        if best_r_idx is not None:
            r = resistance_zones[best_r_idx]
            used_r.add(best_r_idx)
            all_pivots = s.pivots + r.pivots
            all_prices = [p.price for p in all_pivots]
            all_ts = [p.timestamp for p in all_pivots]
            merged.append(Level(
                centroid=float(np.mean(all_prices)),
                top=float(max(all_prices)),
                bottom=float(min(all_prices)),
                role="flip",
                touch_count=len(all_pivots),
                pivots=all_pivots,
                first_tested=min(all_ts),
                last_tested=max(all_ts),
            ))
        else:
            merged.append(s)

    for i, r in enumerate(resistance_zones):
        if i not in used_r:
            merged.append(r)

    return merged
