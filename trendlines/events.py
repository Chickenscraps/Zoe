"""
Structural event detection: breakouts, breakdowns, and retests.

Monitors current price against active trendlines and levels to emit
confirmed structural events with close-count thresholds per timeframe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from trendlines.config import EventsConfig
from trendlines.ransac_fit import FittedLine
from trendlines.dbscan_levels import Level


@dataclass
class StructureEvent:
    """An event emitted when price interacts with a structural feature."""
    symbol: str
    timeframe: str
    event_type: str            # 'breakout' | 'breakdown' | 'retest'
    reference_kind: str        # 'trendline' | 'level'
    reference_id: Optional[int] = None
    price_at: float = 0.0
    confirmed: bool = False
    confirm_count: int = 0
    reason_json: Dict = None

    def __post_init__(self):
        if self.reason_json is None:
            self.reason_json = {}


def detect_structure_events(
    symbol: str,
    timeframe: str,
    closes: List[float],
    trendlines: List[FittedLine],
    levels: List[Level],
    now_ts: float,
    config: Optional[EventsConfig] = None,
    atr: float = 0.0,
) -> List[StructureEvent]:
    """
    Scan for breakouts / breakdowns / retests against active structures.

    Parameters
    ----------
    closes : list[float]
        Recent closing prices (newest last), length >= max(confirm_closes).
    now_ts : float
        Current unix timestamp (for evaluating trendline at this moment).
    """
    cfg = config or EventsConfig()
    events: List[StructureEvent] = []

    required = _required_confirms(timeframe, cfg)
    epsilon_pct = cfg.breakout_epsilon_pct

    # Check levels
    for lv in levels:
        evts = _check_level(symbol, timeframe, closes, lv, required, epsilon_pct, atr)
        events.extend(evts)

    # Check trendlines
    for line in trendlines:
        evts = _check_trendline(symbol, timeframe, closes, line, now_ts, required, epsilon_pct, atr)
        events.extend(evts)

    return events


# ── internal ─────────────────────────────────────────────────────────────

def _required_confirms(tf: str, cfg: EventsConfig) -> int:
    return {
        "15m": cfg.confirm_closes_15m,
        "1h": cfg.confirm_closes_1h,
        "4h": cfg.confirm_closes_4h,
        "1d": 1,
    }.get(tf, 2)


def _check_level(
    symbol: str,
    timeframe: str,
    closes: List[float],
    level: Level,
    required: int,
    epsilon_pct: float,
    atr: float,
) -> List[StructureEvent]:
    events: List[StructureEvent] = []
    if len(closes) < required + 1:
        return events

    recent = closes[-(required + 1):]
    current = recent[-1]
    prev = recent[-2]

    threshold = level.centroid * epsilon_pct if epsilon_pct > 0 else 0

    # Breakout: recent closes above resistance zone
    if level.role in ("resistance", "flip"):
        consecutive_above = sum(1 for c in recent[-required:] if c > level.top + threshold)
        # At least one earlier bar was at/below the zone (context for the cross)
        was_at_or_below = any(c <= level.top + threshold for c in closes[:-required]) if len(closes) > required else True
        if consecutive_above >= required and was_at_or_below:
            events.append(StructureEvent(
                symbol=symbol,
                timeframe=timeframe,
                event_type="breakout",
                reference_kind="level",
                price_at=current,
                confirmed=True,
                confirm_count=consecutive_above,
                reason_json={"level_centroid": level.centroid, "role": level.role},
            ))

    # Breakdown: recent closes below support zone
    if level.role in ("support", "flip"):
        consecutive_below = sum(1 for c in recent[-required:] if c < level.bottom - threshold)
        was_at_or_above = any(c >= level.bottom - threshold for c in closes[:-required]) if len(closes) > required else True
        if consecutive_below >= required and was_at_or_above:
            events.append(StructureEvent(
                symbol=symbol,
                timeframe=timeframe,
                event_type="breakdown",
                reference_kind="level",
                price_at=current,
                confirmed=True,
                confirm_count=consecutive_below,
                reason_json={"level_centroid": level.centroid, "role": level.role},
            ))

    # Retest: price returns to within zone after breaking
    tol = atr * 0.3 if atr > 0 else level.centroid * 0.003
    if level.bottom - tol <= current <= level.top + tol:
        # Check if earlier bars were outside the zone (break + return)
        older = closes[:-(required + 1)] if len(closes) > required + 1 else []
        if older:
            was_below = any(c < level.bottom - tol for c in older[-10:])
            was_above = any(c > level.top + tol for c in older[-10:])
            if was_below or was_above:
                events.append(StructureEvent(
                    symbol=symbol,
                    timeframe=timeframe,
                    event_type="retest",
                    reference_kind="level",
                    price_at=current,
                    confirmed=True,
                    confirm_count=1,
                    reason_json={
                        "level_centroid": level.centroid,
                        "role": level.role,
                        "retest_from": "below" if was_below else "above",
                    },
                ))

    return events


def _check_trendline(
    symbol: str,
    timeframe: str,
    closes: List[float],
    line: FittedLine,
    now_ts: float,
    required: int,
    epsilon_pct: float,
    atr: float,
) -> List[StructureEvent]:
    events: List[StructureEvent] = []
    if len(closes) < required + 1:
        return events

    line_price_now = line.slope * now_ts + line.intercept
    threshold = line_price_now * epsilon_pct if epsilon_pct > 0 else 0
    current = closes[-1]

    if line.side == "support":
        consecutive_below = 0
        for c in closes[-required:]:
            if c < line_price_now - threshold:
                consecutive_below += 1
        if consecutive_below >= required:
            events.append(StructureEvent(
                symbol=symbol,
                timeframe=timeframe,
                event_type="breakdown",
                reference_kind="trendline",
                price_at=current,
                confirmed=True,
                confirm_count=consecutive_below,
                reason_json={
                    "slope": line.slope,
                    "line_price_now": line_price_now,
                    "side": line.side,
                },
            ))

    elif line.side == "resistance":
        consecutive_above = 0
        for c in closes[-required:]:
            if c > line_price_now + threshold:
                consecutive_above += 1
        if consecutive_above >= required:
            events.append(StructureEvent(
                symbol=symbol,
                timeframe=timeframe,
                event_type="breakout",
                reference_kind="trendline",
                price_at=current,
                confirmed=True,
                confirm_count=consecutive_above,
                reason_json={
                    "slope": line.slope,
                    "line_price_now": line_price_now,
                    "side": line.side,
                },
            ))

    return events
