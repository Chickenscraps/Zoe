"""
Robust trendline fitting via Sequential RANSAC.

Implements the "peeling" strategy: fit the dominant line, remove its inliers,
repeat to extract secondary/tertiary structures.  All stochastic steps use a
fixed ``random_state`` for determinism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import numpy as np
from sklearn.linear_model import RANSACRegressor, LinearRegression

from trendlines.pivots import Pivot


def _ransac_loss_name() -> str:
    """Return the correct loss parameter name for the installed sklearn version."""
    import sklearn
    major, minor = [int(x) for x in sklearn.__version__.split(".")[:2]]
    # sklearn >= 1.2 renamed 'absolute_loss' → 'absolute_error'
    if major >= 1 and minor >= 2:
        return "absolute_error"
    return "absolute_loss"


@dataclass
class FittedLine:
    """A single trendline extracted by RANSAC."""
    slope: float
    intercept: float
    side: str              # 'support' | 'resistance'
    inlier_indices: List[int] = field(default_factory=list)
    inlier_pivots: List[Pivot] = field(default_factory=list)
    inlier_count: int = 0
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    residual_threshold: float = 0.0
    score: float = 0.0

    def price_at_time(self, t_numeric: float) -> float:
        """Evaluate the linear model at a given numeric time."""
        return self.slope * t_numeric + self.intercept


def fit_trendlines_sequential(
    pivots: List[Pivot],
    side: str,
    median_atr: float,
    *,
    atr_tol_mult: float = 0.35,
    pct_tol: float = 0.002,
    min_inliers: int = 3,
    max_lines: int = 2,
    max_trials: int = 500,
    random_state: int = 42,
    slope_min_abs: float = 0.0,      # disabled by default; DBSCAN handles horizontals
    recency_cutoff_frac: float = 0.20,
    reference_price: float = 0.0,
) -> List[FittedLine]:
    """
    Sequential (peeling) RANSAC to extract up to *max_lines* trendlines.

    Parameters
    ----------
    pivots : list[Pivot]
        Filtered pivots of matching type (highs for resistance, lows for support).
    side : str
        ``'support'`` or ``'resistance'``.
    median_atr : float
        Median ATR over the analysis window; drives residual_threshold.
    atr_tol_mult : float
        ``residual_threshold = median_atr * atr_tol_mult``.
    pct_tol : float
        Fallback if median_atr is zero/missing.
    min_inliers : int
        Minimum touches for a line to be stored.
    max_lines : int
        Maximum lines to extract per side.
    max_trials : int
        RANSAC iterations.
    random_state : int
        Seed for determinism.
    slope_min_abs : float
        Lines flatter than this (normalised) are discarded (DBSCAN handles
        horizontals).
    recency_cutoff_frac : float
        Fraction of total window; lines whose last inlier is older are
        marked inactive.
    reference_price : float
        Current price for normalising slope; 0 = skip slope filter.

    Returns
    -------
    list[FittedLine]
        Extracted trendlines sorted by inlier count descending.
    """
    if len(pivots) < min_inliers:
        return []

    # Convert pivots → numeric (X = ordinal index, Y = price)
    timestamps = np.array([p.timestamp.timestamp() for p in pivots])
    prices = np.array([p.price for p in pivots])

    # Normalise time axis to [0, N) for numerical stability
    t_min = timestamps.min()
    t_range = timestamps.max() - t_min
    if t_range == 0:
        return []
    X_norm = ((timestamps - t_min) / t_range).reshape(-1, 1)

    # Dynamic residual threshold
    if median_atr > 0:
        threshold = median_atr * atr_tol_mult
    elif reference_price > 0:
        threshold = reference_price * pct_tol
    else:
        threshold = 1.0  # absolute fallback

    remaining_mask = np.ones(len(pivots), dtype=bool)
    results: List[FittedLine] = []

    for _ in range(max_lines):
        active_idx = np.where(remaining_mask)[0]
        if len(active_idx) < min_inliers:
            break

        X_sub = X_norm[active_idx]
        Y_sub = prices[active_idx]

        try:
            ransac = RANSACRegressor(
                estimator=LinearRegression(),
                min_samples=2,
                residual_threshold=threshold,
                max_trials=max_trials,
                loss=_ransac_loss_name(),
                random_state=random_state,
            )
            ransac.fit(X_sub, Y_sub)
        except (ValueError, np.linalg.LinAlgError):
            break

        inlier_mask_sub = ransac.inlier_mask_
        if inlier_mask_sub is None or inlier_mask_sub.sum() < min_inliers:
            break

        inlier_global = active_idx[inlier_mask_sub]

        slope_raw = float(ransac.estimator_.coef_[0])
        intercept_raw = float(ransac.estimator_.intercept_)

        # Convert slope back to price/second units
        slope_real = slope_raw / t_range
        intercept_real = intercept_raw + slope_raw * (-t_min / t_range)
        # But for storage we keep the (normalised-time) model since we
        # evaluate via ``price_at_time(t_numeric)``.
        # The *stored* slope/intercept use original timestamps:
        #   price = slope_real * unix_ts + intercept_real
        # This is reconstructible: y = (slope_raw/t_range)*(t - t_min) + intercept_raw
        # => y = slope_raw/t_range * t - slope_raw*t_min/t_range + intercept_raw

        inlier_pivots = [pivots[i] for i in inlier_global]
        start_at = min(p.timestamp for p in inlier_pivots)
        end_at = max(p.timestamp for p in inlier_pivots)

        # Slope filter: skip near-horizontal lines (DBSCAN handles those)
        if reference_price > 0 and slope_min_abs > 0:
            # Price change per unit-normalised-time
            # slope_raw is price/normalised_unit
            norm_slope = abs(slope_raw) / reference_price
            if norm_slope < slope_min_abs:
                # Peel anyway so we don't loop forever
                remaining_mask[inlier_global] = False
                continue

        line = FittedLine(
            slope=slope_real,
            intercept=intercept_real,
            side=side,
            inlier_indices=inlier_global.tolist(),
            inlier_pivots=inlier_pivots,
            inlier_count=len(inlier_global),
            start_at=start_at,
            end_at=end_at,
            residual_threshold=threshold,
        )
        results.append(line)

        # Peel inliers
        remaining_mask[inlier_global] = False

    results.sort(key=lambda l: l.inlier_count, reverse=True)
    return results
