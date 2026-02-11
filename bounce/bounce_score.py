"""
Quantitative bounce scoring (0-100).

Components (from research doc):
  ATR Spike:       max 25 pts
  Volume Spike:    max 20 pts
  Wick Ratio:      max 20 pts
  Stabilization:   max 20 pts  (10 per confirmation, max 2 counted)
  Funding:         max 15 pts

Total theoretical max = 100.
"""

from __future__ import annotations

from typing import Any, Dict, List


def calculate_bounce_score(
    cap_metrics: Dict[str, Any],
    confirmations: List[str],
    indicators: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute the bounce score and return component breakdown.

    Parameters
    ----------
    cap_metrics : dict
        Output of ``detect_capitulation_event`` (tr, atr, vol, vol_ma, wick_ratio).
    confirmations : list[str]
        List of stabilization confirmations that fired.
    indicators : dict
        External signals (``funding_8h``, etc.).

    Returns
    -------
    dict with ``score`` (int) and ``components`` (dict of component → points).
    """
    score = 0
    components: Dict[str, int] = {}

    tr = float(cap_metrics.get("tr", 0))
    atr = float(cap_metrics.get("atr", 1))  # avoid div-zero
    vol = float(cap_metrics.get("vol", 0))
    vol_ma = float(cap_metrics.get("vol_ma", 1))
    wick_ratio = float(cap_metrics.get("wick_ratio", 0))

    # 1. Range spike (max 25)
    atr_ratio = tr / atr if atr > 0 else 0
    range_pts = min(25, int(atr_ratio * 10))
    score += range_pts
    components["range_spike"] = range_pts

    # 2. Volume spike (max 20)
    vol_ratio = vol / vol_ma if vol_ma > 0 else 0
    vol_pts = min(20, int(vol_ratio * 10))
    score += vol_pts
    components["volume_spike"] = vol_pts

    # 3. Wick ratio (max 20)
    wick_pts = min(20, int(wick_ratio * 40))
    score += wick_pts
    components["wick_ratio"] = wick_pts

    # 4. Stabilization (max 20, 10 pts per confirmation, cap at 2)
    stab_count = min(len(confirmations), 2)
    stab_pts = stab_count * 10
    score += stab_pts
    components["stabilization"] = stab_pts

    # 5. Funding (max 15)
    funding = indicators.get("funding_8h")
    funding_pts = 0
    if funding is not None:
        try:
            if float(funding) <= 0:
                funding_pts = 15
        except (ValueError, TypeError):
            pass
    score += funding_pts
    components["funding"] = funding_pts

    return {"score": min(score, 100), "components": components}
