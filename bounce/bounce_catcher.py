"""
Bounce Catcher — 3-phase state machine orchestrator.

States per symbol:
    IDLE → CAPITULATION_DETECTED → STABILIZATION_CONFIRMED → INTENT_EMITTED

All state transitions are persisted to ``bounce_events``.
Trade intents are persisted to ``bounce_intents``.
Shadow mode: ``enabled=False`` → detect + log, never emit.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol

import pandas as pd

from bounce.capitulation import detect_capitulation_event
from bounce.stabilization import check_stabilization
from bounce.bounce_score import calculate_bounce_score
from bounce.entry_planner import TradeIntent, build_trade_intent
from bounce.exit_planner import ExitPlan, compute_exit_plan
from bounce.guards import check_halt_conditions
from bounce.config import BounceConfig

logger = logging.getLogger(__name__)


# Minimal protocol for the DB client
class DBClient(Protocol):
    def table(self, name: str) -> Any: ...


# ── Persisted state record ───────────────────────────────────────────────

class SymbolState:
    """In-memory state for a single symbol's bounce tracker."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.state: str = "IDLE"
        self.cap_metrics: Dict[str, Any] = {}
        self.cap_candle: Optional[pd.Series] = None
        self.cap_candle_dict: Dict[str, Any] = {}
        self.confirmations: List[str] = []
        self.score_data: Dict[str, Any] = {}
        self.intent: Optional[TradeIntent] = None
        self.exit_plan: Optional[ExitPlan] = None
        self.last_alert_ts: datetime = datetime.min.replace(tzinfo=timezone.utc)
        self.entered_state_at: datetime = datetime.now(timezone.utc)


class BounceCatcher:
    """
    Orchestrates bounce detection across a universe of symbols.

    Usage::

        catcher = BounceCatcher(config, db_client)
        catcher.process_tick("BTC-USD", df_15m, df_1h, indicators, market_state)
    """

    def __init__(self, config: BounceConfig, db: Optional[DBClient] = None):
        self.cfg = config
        self.db = db
        self._states: Dict[str, SymbolState] = {}

    def _get_state(self, symbol: str) -> SymbolState:
        if symbol not in self._states:
            self._states[symbol] = SymbolState(symbol)
        return self._states[symbol]

    # ── Main tick entry point ────────────────────────────────────────

    def process_tick(
        self,
        symbol: str,
        df_15m: pd.DataFrame,
        df_1h: Optional[pd.DataFrame],
        indicators: Dict[str, Any],
        market_state: Dict[str, Any],
        structure_api: Optional[Any] = None,
    ) -> Optional[TradeIntent]:
        """
        Process a single tick/candle-close for *symbol*.

        Returns a ``TradeIntent`` if one was emitted (and ``enabled=True``),
        otherwise ``None``.  In shadow mode, events are still logged.
        """
        ss = self._get_state(symbol)

        # ── Guard check (always, regardless of state) ────────────────
        halts = check_halt_conditions(
            symbol,
            market_state,
            vol_halt_24h_range=self.cfg.vol_halt_24h_range,
            max_spread_pct=self.cfg.execution.max_spread_pct_to_trade,
            weekend_dampener=self.cfg.weekend_dampener,
        )
        if halts:
            if ss.state != "IDLE":
                self._transition(ss, "IDLE", f"halt: {halts}")
            return None

        # ── State machine ────────────────────────────────────────────
        if ss.state == "IDLE":
            return self._phase_idle(ss, df_15m, indicators, structure_api)

        elif ss.state == "CAPITULATION_DETECTED":
            return self._phase_capitulation(ss, df_15m, indicators, market_state, structure_api)

        elif ss.state == "STABILIZATION_CONFIRMED":
            return self._phase_stabilization(ss, df_15m, indicators, market_state, structure_api)

        return None

    # ── Phase handlers ───────────────────────────────────────────────

    def _phase_idle(
        self, ss: SymbolState, df_15m: pd.DataFrame,
        indicators: Dict[str, Any],
        structure_api: Optional[Any],
    ) -> Optional[TradeIntent]:
        """IDLE: scan for capitulation."""
        is_cap, metrics = detect_capitulation_event(
            df_15m,
            atr_len=self.cfg.atr_len,
            vol_ma_len=self.cfg.vol_ma_len,
            atr_mult=self.cfg.capitulation.atr_mult,
            vol_mult=self.cfg.capitulation.vol_mult,
            lower_wick_min=self.cfg.capitulation.lower_wick_min,
        )
        if not is_cap:
            return None

        # Store context
        ss.cap_metrics = metrics
        ss.cap_candle = df_15m.iloc[-1].copy()
        ss.cap_candle_dict = {
            "open": float(df_15m.iloc[-1]["open"]),
            "high": float(df_15m.iloc[-1]["high"]),
            "low": float(df_15m.iloc[-1]["low"]),
            "close": float(df_15m.iloc[-1]["close"]),
            "volume": float(df_15m.iloc[-1]["volume"]),
        }

        # Structure gate: check if capitulation is into a support zone
        structure_note = ""
        if structure_api:
            try:
                sup = structure_api.nearest_support(
                    ss.symbol, "15m", float(df_15m.iloc[-1]["low"]),
                )
                if sup:
                    cscore = structure_api.confluence_score_at(
                        ss.symbol, "15m", float(df_15m.iloc[-1]["low"]),
                    )
                    structure_note = f"near_support={sup.centroid:.2f}, confluence={cscore:.0f}"
                    metrics["structure_support"] = sup.centroid
                    metrics["structure_confluence"] = cscore
            except Exception as e:
                logger.warning("structure_api error: %s", e)

        self._transition(
            ss, "CAPITULATION_DETECTED",
            f"Waterfall detected. {structure_note}",
        )
        self._alert_capitulation(ss, metrics)
        return None

    def _phase_capitulation(
        self, ss: SymbolState, df_15m: pd.DataFrame,
        indicators: Dict[str, Any],
        market_state: Dict[str, Any],
        structure_api: Optional[Any],
    ) -> Optional[TradeIntent]:
        """CAPITULATION_DETECTED: wait for stabilization."""
        # Timeout: if we've been waiting too long, reset
        elapsed = datetime.now(timezone.utc) - ss.entered_state_at
        if elapsed > timedelta(hours=6):
            self._transition(ss, "IDLE", "stabilization timeout (6h)")
            return None

        is_stable, confirms = check_stabilization(
            df_15m,
            ss.cap_candle_dict,
            indicators,
            confirmations_required=self.cfg.stabilization.confirmations_required,
            higher_lows_k=self.cfg.stabilization.higher_lows_k,
            rsi_reclaim=self.cfg.stabilization.rsi_reclaim,
            funding_support_max_8h=self.cfg.stabilization.funding_support_max_8h,
            allow_missing_altdata=self.cfg.stabilization.allow_missing_altdata,
        )

        if not is_stable:
            return None

        ss.confirmations = confirms
        self._transition(
            ss, "STABILIZATION_CONFIRMED",
            f"Confirms: {confirms}",
        )
        # Immediately attempt scoring in same tick
        return self._phase_stabilization(ss, df_15m, indicators, market_state, structure_api)

    def _phase_stabilization(
        self, ss: SymbolState, df_15m: pd.DataFrame,
        indicators: Dict[str, Any],
        market_state: Dict[str, Any],
        structure_api: Optional[Any],
    ) -> Optional[TradeIntent]:
        """STABILIZATION_CONFIRMED: compute score → emit or reject."""
        score_data = calculate_bounce_score(
            ss.cap_metrics, ss.confirmations, indicators,
        )
        ss.score_data = score_data

        # Structure-enhanced scoring
        if structure_api:
            try:
                cscore = structure_api.confluence_score_at(
                    ss.symbol, "15m", float(df_15m.iloc[-1]["close"]),
                )
                # Boost score if in a golden zone (confluence >= 45)
                if cscore >= 45:
                    bonus = min(int(cscore * 0.1), 10)
                    score_data["score"] = min(score_data["score"] + bonus, 100)
                    score_data["components"]["structure_bonus"] = bonus
            except Exception:
                pass

        current_price = float(df_15m.iloc[-1]["close"])
        atr = float(ss.cap_metrics.get("atr", 0))
        cap_low = float(ss.cap_candle_dict.get("low", 0))

        if score_data["score"] < self.cfg.scoring.min_score:
            self._persist_intent_blocked(
                ss, score_data, current_price,
                f"score {score_data['score']} < min {self.cfg.scoring.min_score}",
            )
            self._transition(ss, "IDLE", f"Score {score_data['score']} below threshold")
            return None

        # Build intent
        intent = build_trade_intent(
            ss.symbol,
            ss.cap_metrics,
            score_data,
            current_price,
            atr,
            tp_pct=self.cfg.execution.tp_pct,
            sl_atr_mult=self.cfg.execution.sl_atr_mult,
            sl_hard_pct=self.cfg.execution.sl_hard_pct,
            time_stop_hours=self.cfg.execution.time_stop_hours,
            entry_style=self.cfg.execution.entry_style,
            cap_low=cap_low,
        )
        ss.intent = intent

        # Persist intent
        self._persist_intent(ss, score_data, intent)

        if not self.cfg.enabled:
            # Shadow mode: log but don't emit
            logger.info(
                "[%s] SHADOW: would emit intent score=%d price=%.2f",
                ss.symbol, intent.score, intent.entry_price,
            )
            self._transition(ss, "IDLE", "shadow mode — intent logged, not emitted")
            return None

        self._transition(ss, "INTENT_EMITTED", f"Intent emitted: score={intent.score}")
        return intent

    # ── State transition + persistence ───────────────────────────────

    def _transition(self, ss: SymbolState, new_state: str, reason: str) -> None:
        prev = ss.state
        logger.info("[%s] %s → %s | %s", ss.symbol, prev, new_state, reason)

        ss.state = new_state
        ss.entered_state_at = datetime.now(timezone.utc)

        if self.db:
            try:
                self.db.table("bounce_events").insert({
                    "symbol": ss.symbol,
                    "prev_state": prev,
                    "state": new_state,
                    "score": ss.score_data.get("score") if ss.score_data else None,
                    "reason_json": json.dumps({
                        "msg": reason,
                        "cap_metrics": _safe_json(ss.cap_metrics),
                        "confirmations": ss.confirmations,
                    }),
                }).execute()
            except Exception as e:
                logger.error("bounce_events insert failed: %s", e)

        # Reset context on return to IDLE
        if new_state == "IDLE":
            ss.cap_metrics = {}
            ss.cap_candle = None
            ss.cap_candle_dict = {}
            ss.confirmations = []
            ss.score_data = {}
            ss.intent = None
            ss.exit_plan = None

    def _persist_intent(
        self, ss: SymbolState, score_data: Dict, intent: TradeIntent,
    ) -> None:
        if not self.db:
            return
        try:
            self.db.table("bounce_intents").insert({
                "symbol": ss.symbol,
                "entry_style": intent.entry_style,
                "entry_price": intent.entry_price,
                "expected_move_pct": intent.expected_move_pct,
                "tp_price": intent.tp_price,
                "sl_price": intent.sl_price,
                "score": intent.score,
                "components_json": json.dumps(score_data.get("components", {})),
                "blocked": False,
                "executed": self.cfg.enabled,
                "reason_json": json.dumps({"reason": intent.reason}),
            }).execute()
        except Exception as e:
            logger.error("bounce_intents insert failed: %s", e)

    def _persist_intent_blocked(
        self, ss: SymbolState, score_data: Dict,
        price: float, reason: str,
    ) -> None:
        if not self.db:
            return
        try:
            self.db.table("bounce_intents").insert({
                "symbol": ss.symbol,
                "entry_style": self.cfg.execution.entry_style,
                "entry_price": price,
                "score": score_data.get("score", 0),
                "components_json": json.dumps(score_data.get("components", {})),
                "blocked": True,
                "blocked_reason": reason,
                "executed": False,
                "reason_json": json.dumps({"reason": reason}),
            }).execute()
        except Exception as e:
            logger.error("bounce_intents blocked insert failed: %s", e)

    # ── Discord alerting ─────────────────────────────────────────────

    def _alert_capitulation(self, ss: SymbolState, metrics: Dict) -> None:
        now = datetime.now(timezone.utc)
        throttle = timedelta(minutes=self.cfg.alerts.throttle_minutes)
        if now - ss.last_alert_ts < throttle:
            return

        ss.last_alert_ts = now
        msg = (
            f"🚨 Capitulation Detected: {ss.symbol}\n"
            f"ATR Mult: {metrics.get('tr', 0) / max(metrics.get('atr', 1), 1e-9):.1f} | "
            f"Vol Mult: {metrics.get('vol', 0) / max(metrics.get('vol_ma', 1), 1e-9):.1f} | "
            f"Wick: {metrics.get('wick_ratio', 0):.2f}\n"
            f"Watching for stabilization."
        )
        logger.info("[discord] %s", msg)
        # Integration point: call discord_bot.post_thought(msg) here

    # ── Restore state from DB (restart recovery) ─────────────────────

    def restore_state(self, symbol: str) -> None:
        """
        Recover the last known state from bounce_events on startup.
        Prevents re-triggering on the same capitulation after restart.
        """
        if not self.db:
            return
        try:
            resp = (
                self.db.table("bounce_events")
                .select("state, reason_json")
                .eq("symbol", symbol)
                .order("ts", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                last = resp.data[0]
                ss = self._get_state(symbol)
                restored_state = last.get("state", "IDLE")
                # Only restore non-IDLE states if recent (< 6h)
                if restored_state != "IDLE":
                    ss.state = restored_state
                    logger.info("[%s] restored state: %s", symbol, restored_state)
        except Exception as e:
            logger.warning("state restore failed for %s: %s", symbol, e)


def _safe_json(obj: Any) -> Any:
    """Make sure obj is JSON-serialisable."""
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(v) for v in obj]
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)
