"""
Supabase persistence layer for trendlines module.

Handles upserting pivots, trendlines, levels, and events.
Uses insert-only append for events, upsert-by-proximity for levels.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from trendlines.pivots import Pivot
from trendlines.ransac_fit import FittedLine
from trendlines.dbscan_levels import Level
from trendlines.events import StructureEvent

logger = logging.getLogger(__name__)


class SupabaseClient(Protocol):
    """Minimal protocol so we can inject any Supabase-like client or mock."""
    def table(self, name: str) -> Any: ...


class TrendlinePersistence:
    """Reads/writes trendline module data to Supabase."""

    def __init__(self, db: SupabaseClient):
        self.db = db

    # ── Pivots ────────────────────────────────────────────────────────

    def upsert_pivots(self, symbol: str, timeframe: str, pivots: List[Pivot]) -> int:
        """Upsert confirmed pivots.  Returns number of rows written."""
        if not pivots:
            return 0

        rows = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": p.timestamp.isoformat(),
                "price": p.price,
                "type": p.type,
                "source": p.source,
                "atr_snapshot": p.atr_snapshot,
                "confirmed": True,
            }
            for p in pivots
        ]

        try:
            self.db.table("market_pivots").upsert(
                rows,
                on_conflict="symbol,timeframe,timestamp,type,source",
            ).execute()
            return len(rows)
        except Exception as e:
            logger.error("pivot upsert failed: %s", e)
            return 0

    def fetch_pivots(
        self, symbol: str, timeframe: str, limit: int = 300
    ) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.db.table("market_pivots")
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .eq("confirmed", True)
                .order("timestamp", desc=True)
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error("pivot fetch failed: %s", e)
            return []

    # ── Trendlines ────────────────────────────────────────────────────

    def save_trendlines(
        self, symbol: str, timeframe: str, lines: List[FittedLine]
    ) -> None:
        """Mark all old active lines inactive, then insert new batch."""
        try:
            # Deactivate previous
            self.db.table("technical_trendlines").update(
                {"is_active": False, "updated_at": _now_iso()}
            ).eq("symbol", symbol).eq("timeframe", timeframe).eq(
                "is_active", True
            ).execute()
        except Exception as e:
            logger.warning("trendline deactivation failed: %s", e)

        if not lines:
            return

        rows = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "side": line.side,
                "slope": line.slope,
                "intercept": line.intercept,
                "start_at": line.start_at.isoformat() if line.start_at else _now_iso(),
                "end_at": line.end_at.isoformat() if line.end_at else _now_iso(),
                "inlier_count": line.inlier_count,
                "score": line.score,
                "metadata": json.dumps({
                    "inlier_indices": line.inlier_indices[:50],  # cap size
                    "residual_threshold": line.residual_threshold,
                }),
                "is_active": True,
            }
            for line in lines
        ]

        try:
            self.db.table("technical_trendlines").insert(rows).execute()
        except Exception as e:
            logger.error("trendline insert failed: %s", e)

    # ── Levels ────────────────────────────────────────────────────────

    def save_levels(
        self, symbol: str, timeframe: str, levels: List[Level]
    ) -> None:
        """Deactivate old, insert new (simple replacement strategy)."""
        try:
            self.db.table("technical_levels").update(
                {"is_active": False, "updated_at": _now_iso()}
            ).eq("symbol", symbol).eq("timeframe", timeframe).eq(
                "is_active", True
            ).execute()
        except Exception as e:
            logger.warning("level deactivation failed: %s", e)

        if not levels:
            return

        rows = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "price_centroid": lv.centroid,
                "price_top": lv.top,
                "price_bottom": lv.bottom,
                "role": lv.role,
                "touch_count": lv.touch_count,
                "score": lv.score,
                "first_tested": lv.first_tested.isoformat() if lv.first_tested else None,
                "last_tested": lv.last_tested.isoformat() if lv.last_tested else None,
                "is_active": True,
                "metadata": json.dumps(lv.metadata),
            }
            for lv in levels
        ]

        try:
            self.db.table("technical_levels").insert(rows).execute()
        except Exception as e:
            logger.error("level insert failed: %s", e)

    def fetch_active_levels(
        self, symbol: str, timeframe: str
    ) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.db.table("technical_levels")
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .eq("is_active", True)
                .order("score", desc=True)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error("level fetch failed: %s", e)
            return []

    # ── Events ────────────────────────────────────────────────────────

    def insert_event(self, event: StructureEvent) -> None:
        row = {
            "symbol": event.symbol,
            "timeframe": event.timeframe,
            "event_type": event.event_type,
            "reference_kind": event.reference_kind,
            "reference_id": event.reference_id,
            "price_at": event.price_at,
            "confirmed": event.confirmed,
            "confirm_count": event.confirm_count,
            "reason_json": json.dumps(event.reason_json),
        }
        try:
            self.db.table("structure_events").insert(row).execute()
        except Exception as e:
            logger.error("event insert failed: %s", e)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
