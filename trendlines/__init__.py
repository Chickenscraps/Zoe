"""
Trendlines + Key Levels module for the Zoe Trading System.

Provides deterministic detection, scoring, and persistence of market structure
using RANSAC trendline fitting and DBSCAN horizontal level clustering.
"""

from trendlines.pivots import detect_pivots_vectorized, filter_pivots_by_atr
from trendlines.ransac_fit import fit_trendlines_sequential
from trendlines.dbscan_levels import cluster_levels
from trendlines.scoring import score_trendline, score_level
from trendlines.events import detect_structure_events
from trendlines.api import StructureAPI

__all__ = [
    "detect_pivots_vectorized",
    "filter_pivots_by_atr",
    "fit_trendlines_sequential",
    "cluster_levels",
    "score_trendline",
    "score_level",
    "detect_structure_events",
    "StructureAPI",
]
