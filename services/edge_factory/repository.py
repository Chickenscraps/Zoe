from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Protocol

from .models import EdgePosition, FeatureSnapshot, RegimeState, Signal


class FeatureRepository(Protocol):
    """Interface for Edge Factory data persistence."""

    # ── Features ──────────────────────────────────────────────
    def insert_feature(self, feature: FeatureSnapshot) -> None: ...
    def get_latest_feature(self, symbol: str, feature_name: str) -> FeatureSnapshot | None: ...
    def get_feature_history(self, symbol: str, feature_name: str, limit: int = 100) -> list[FeatureSnapshot]: ...

    # ── Regimes ───────────────────────────────────────────────
    def insert_regime(self, regime: RegimeState) -> str: ...
    def get_latest_regime(self) -> RegimeState | None: ...

    # ── Signals ───────────────────────────────────────────────
    def insert_signal(self, signal: Signal) -> str: ...
    def get_recent_signals(self, symbol: str, limit: int = 10) -> list[Signal]: ...

    # ── Positions ─────────────────────────────────────────────
    def insert_position(self, position: EdgePosition) -> str: ...
    def update_position(self, position_id: str, updates: dict[str, Any]) -> None: ...
    def get_open_positions(self) -> list[EdgePosition]: ...
    def get_closed_positions(self, limit: int = 20) -> list[EdgePosition]: ...

    # ── State (kill switch, circuit breaker, etc.) ────────────
    def get_state(self, key: str) -> Any: ...
    def set_state(self, key: str, value: Any) -> None: ...

    # ── Metrics ───────────────────────────────────────────────
    def get_daily_notional(self, day: date) -> float: ...
    def set_daily_notional(self, day: date, amount: float) -> None: ...
    def get_equity_high_water_mark(self) -> float: ...
    def set_equity_high_water_mark(self, value: float) -> None: ...


# ══════════════════════════════════════════════════════════════
# In-Memory Implementation (for testing)
# ══════════════════════════════════════════════════════════════


class InMemoryFeatureRepository:
    """In-memory implementation for unit testing."""

    def __init__(self) -> None:
        self.features: list[FeatureSnapshot] = []
        self.regimes: list[RegimeState] = []
        self.signals: list[Signal] = []
        self.positions: list[EdgePosition] = []
        self.state: dict[str, Any] = {}
        self.daily_notional: dict[str, float] = {}

    # ── Features ──────────────────────────────────────────────

    def insert_feature(self, feature: FeatureSnapshot) -> None:
        self.features.append(feature)

    def get_latest_feature(self, symbol: str, feature_name: str) -> FeatureSnapshot | None:
        matches = [
            f for f in self.features
            if f.symbol == symbol and f.feature_name == feature_name
        ]
        if not matches:
            return None
        return max(matches, key=lambda f: f.computed_at)

    def get_feature_history(self, symbol: str, feature_name: str, limit: int = 100) -> list[FeatureSnapshot]:
        matches = [
            f for f in self.features
            if f.symbol == symbol and f.feature_name == feature_name
        ]
        matches.sort(key=lambda f: f.computed_at, reverse=True)
        return matches[:limit]

    # ── Regimes ───────────────────────────────────────────────

    def insert_regime(self, regime: RegimeState) -> str:
        regime_id = str(uuid.uuid4())
        self.regimes.append(regime)
        return regime_id

    def get_latest_regime(self) -> RegimeState | None:
        if not self.regimes:
            return None
        return max(self.regimes, key=lambda r: r.detected_at)

    # ── Signals ───────────────────────────────────────────────

    def insert_signal(self, signal: Signal) -> str:
        signal_id = signal.signal_id or str(uuid.uuid4())
        signal.signal_id = signal_id
        self.signals.append(signal)
        return signal_id

    def get_recent_signals(self, symbol: str, limit: int = 10) -> list[Signal]:
        matches = [s for s in self.signals if s.symbol == symbol]
        matches.sort(key=lambda s: s.generated_at, reverse=True)
        return matches[:limit]

    # ── Positions ─────────────────────────────────────────────

    def insert_position(self, position: EdgePosition) -> str:
        position_id = position.position_id or str(uuid.uuid4())
        position.position_id = position_id
        self.positions.append(position)
        return position_id

    def update_position(self, position_id: str, updates: dict[str, Any]) -> None:
        for pos in self.positions:
            if pos.position_id == position_id:
                for key, val in updates.items():
                    if hasattr(pos, key):
                        setattr(pos, key, val)
                return

    def get_open_positions(self) -> list[EdgePosition]:
        return [p for p in self.positions if p.is_open()]

    def get_closed_positions(self, limit: int = 20) -> list[EdgePosition]:
        closed = [p for p in self.positions if not p.is_open()]
        closed.sort(key=lambda p: p.exit_time or p.entry_time, reverse=True)
        return closed[:limit]

    # ── State ─────────────────────────────────────────────────

    def get_state(self, key: str) -> Any:
        return self.state.get(key)

    def set_state(self, key: str, value: Any) -> None:
        self.state[key] = value

    # ── Metrics ───────────────────────────────────────────────

    def get_daily_notional(self, day: date) -> float:
        return self.daily_notional.get(str(day), 0.0)

    def set_daily_notional(self, day: date, amount: float) -> None:
        self.daily_notional[str(day)] = amount

    def get_equity_high_water_mark(self) -> float:
        return self.state.get("equity_hwm", 150.0)

    def set_equity_high_water_mark(self, value: float) -> None:
        self.state["equity_hwm"] = value


# ══════════════════════════════════════════════════════════════
# Supabase Implementation (production)
# ══════════════════════════════════════════════════════════════


class SupabaseFeatureRepository:
    """Production implementation using existing Supabase instance."""

    def __init__(self, mode: str = "live") -> None:
        from supabase import create_client

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_KEY", ""))
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        self.client = create_client(url, key)
        self.mode = mode

    # ── Features ──────────────────────────────────────────────

    def insert_feature(self, feature: FeatureSnapshot) -> None:
        self.client.table("ef_features").insert({
            "mode": self.mode,
            "symbol": feature.symbol,
            "feature_name": feature.feature_name,
            "value": feature.value,
            "computed_at": feature.computed_at.isoformat(),
            "source": feature.source,
            "metadata": feature.metadata,
        }).execute()

    def get_latest_feature(self, symbol: str, feature_name: str) -> FeatureSnapshot | None:
        resp = (
            self.client.table("ef_features")
            .select("*")
            .eq("mode", self.mode)
            .eq("symbol", symbol)
            .eq("feature_name", feature_name)
            .order("computed_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data
        if not rows:
            return None
        row = rows[0]
        return FeatureSnapshot(
            symbol=row["symbol"],
            feature_name=row["feature_name"],
            value=float(row["value"]),
            computed_at=datetime.fromisoformat(row["computed_at"]),
            source=row["source"],
            metadata=row.get("metadata") or {},
        )

    def get_feature_history(self, symbol: str, feature_name: str, limit: int = 100) -> list[FeatureSnapshot]:
        resp = (
            self.client.table("ef_features")
            .select("*")
            .eq("mode", self.mode)
            .eq("symbol", symbol)
            .eq("feature_name", feature_name)
            .order("computed_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [
            FeatureSnapshot(
                symbol=r["symbol"],
                feature_name=r["feature_name"],
                value=float(r["value"]),
                computed_at=datetime.fromisoformat(r["computed_at"]),
                source=r["source"],
                metadata=r.get("metadata") or {},
            )
            for r in resp.data
        ]

    # ── Regimes ───────────────────────────────────────────────

    def insert_regime(self, regime: RegimeState) -> str:
        regime_id = str(uuid.uuid4())
        self.client.table("ef_regimes").insert({
            "id": regime_id,
            "mode": self.mode,
            "regime": regime.regime,
            "confidence": regime.confidence,
            "detected_at": regime.detected_at.isoformat(),
            "features_used": regime.features_used,
        }).execute()
        return regime_id

    def get_latest_regime(self) -> RegimeState | None:
        resp = (
            self.client.table("ef_regimes")
            .select("*")
            .eq("mode", self.mode)
            .order("detected_at", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        r = resp.data[0]
        return RegimeState(
            regime=r["regime"],
            confidence=float(r["confidence"]),
            detected_at=datetime.fromisoformat(r["detected_at"]),
            features_used=r.get("features_used") or {},
        )

    # ── Signals ───────────────────────────────────────────────

    def insert_signal(self, signal: Signal) -> str:
        signal_id = signal.signal_id or str(uuid.uuid4())
        self.client.table("ef_signals").insert({
            "id": signal_id,
            "mode": self.mode,
            "symbol": signal.symbol,
            "direction": signal.direction,
            "strength": signal.strength,
            "features": signal.features,
            "generated_at": signal.generated_at.isoformat(),
            "strategy_name": signal.strategy_name,
            "acted_on": False,
        }).execute()
        return signal_id

    def get_recent_signals(self, symbol: str, limit: int = 10) -> list[Signal]:
        resp = (
            self.client.table("ef_signals")
            .select("*")
            .eq("mode", self.mode)
            .eq("symbol", symbol)
            .order("generated_at", desc=True)
            .limit(limit)
            .execute()
        )
        results = []
        for r in resp.data:
            regime = self.get_latest_regime() or RegimeState(regime="unknown", confidence=0.0)
            results.append(Signal(
                symbol=r["symbol"],
                direction=r["direction"],
                strength=float(r["strength"]),
                regime=regime,
                features=r.get("features") or {},
                generated_at=datetime.fromisoformat(r["generated_at"]),
                strategy_name=r["strategy_name"],
                signal_id=r["id"],
            ))
        return results

    # ── Positions ─────────────────────────────────────────────

    def insert_position(self, position: EdgePosition) -> str:
        position_id = position.position_id or str(uuid.uuid4())
        self.client.table("ef_positions").insert({
            "id": position_id,
            "mode": self.mode,
            "symbol": position.symbol,
            "side": position.side,
            "entry_price": position.entry_price,
            "entry_time": position.entry_time.isoformat(),
            "size_usd": position.size_usd,
            "tp_price": position.tp_price,
            "sl_price": position.sl_price,
            "status": position.status,
            "signal_id": position.signal_id or None,
            "order_id": position.order_id,
        }).execute()
        return position_id

    def update_position(self, position_id: str, updates: dict[str, Any]) -> None:
        # Convert datetime fields to ISO strings for Supabase
        clean = {}
        for k, v in updates.items():
            if isinstance(v, datetime):
                clean[k] = v.isoformat()
            else:
                clean[k] = v
        self.client.table("ef_positions").update(clean).eq("id", position_id).execute()

    def get_open_positions(self) -> list[EdgePosition]:
        resp = (
            self.client.table("ef_positions")
            .select("*")
            .eq("mode", self.mode)
            .in_("status", ["pending", "open"])
            .execute()
        )
        return [self._row_to_position(r) for r in resp.data]

    def get_closed_positions(self, limit: int = 20) -> list[EdgePosition]:
        resp = (
            self.client.table("ef_positions")
            .select("*")
            .eq("mode", self.mode)
            .not_.in_("status", ["pending", "open"])
            .order("exit_time", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_position(r) for r in resp.data]

    def _row_to_position(self, r: dict[str, Any]) -> EdgePosition:
        return EdgePosition(
            symbol=r["symbol"],
            side=r.get("side", "buy"),
            entry_price=float(r.get("entry_price") or 0),
            entry_time=datetime.fromisoformat(r["entry_time"]) if r.get("entry_time") else datetime.now(timezone.utc),
            size_usd=float(r.get("size_usd") or 0),
            tp_price=float(r.get("tp_price") or 0),
            sl_price=float(r.get("sl_price") or 0),
            status=r.get("status", "pending"),
            exit_price=float(r["exit_price"]) if r.get("exit_price") is not None else None,
            exit_time=datetime.fromisoformat(r["exit_time"]) if r.get("exit_time") else None,
            pnl_usd=float(r["pnl_usd"]) if r.get("pnl_usd") is not None else None,
            signal_id=r.get("signal_id") or "",
            order_id=r.get("order_id"),
            position_id=r.get("id", ""),
        )

    # ── State ─────────────────────────────────────────────────

    def get_state(self, key: str) -> Any:
        resp = (
            self.client.table("ef_state")
            .select("value")
            .eq("mode", self.mode)
            .eq("key", key)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return resp.data[0]["value"]

    def set_state(self, key: str, value: Any) -> None:
        self.client.table("ef_state").upsert({
            "mode": self.mode,
            "key": key,
            "value": json.dumps(value) if not isinstance(value, str) else value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

    # ── Metrics ───────────────────────────────────────────────

    def get_daily_notional(self, day: date) -> float:
        val = self.get_state(f"daily_notional_{day}")
        if val is None:
            return 0.0
        return float(json.loads(val) if isinstance(val, str) else val)

    def set_daily_notional(self, day: date, amount: float) -> None:
        self.set_state(f"daily_notional_{day}", amount)

    def get_equity_high_water_mark(self) -> float:
        val = self.get_state("equity_hwm")
        if val is None:
            return 150.0
        return float(json.loads(val) if isinstance(val, str) else val)

    def set_equity_high_water_mark(self, value: float) -> None:
        self.set_state("equity_hwm", value)
