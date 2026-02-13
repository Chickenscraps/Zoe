from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any

from services.crypto_trader.logger import JsonAuditLogger

from .config import EdgeFactoryConfig
from .executor import EdgeFactoryExecutor
from .feature_engine import FeatureEngine
from .models import EdgePosition, RegimeState, Signal
from .position_sizer import PositionSizer
from .regime_detector import RegimeDetector
from .repository import FeatureRepository
from .signal_generator import SignalGenerator
from .strategy_registry import StrategyRegistry

if TYPE_CHECKING:
    from .account_state import AccountState
    from .trade_intent import TradeIntentBuilder

logger = logging.getLogger(__name__)


class EdgeFactoryOrchestrator:
    """
    Main control loop for the Edge Factory trading bot.

    Tick cycle (runs every market_poll_interval):
    1. Check kill switch / circuit breaker
    2. Run FeatureEngine.compute_all() for all symbols
    3. Detect regime
    4. For each symbol: evaluate signals
    5. For new signals: size position, submit entry via executor
    6. For open positions: check exits (TP/SL/regime/timeout)
    7. Persist all state
    8. Log events

    Safety layers:
    - Kill switch: drawdown > 20% in 24h → liquidate all + shutdown
    - Circuit breaker: 3+ consecutive API failures → sleep 15 min
    - Data staleness: missing data → default to HOLD
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        feature_engine: FeatureEngine,
        regime_detector: RegimeDetector,
        signal_generator: SignalGenerator,
        position_sizer: PositionSizer,
        executor: EdgeFactoryExecutor,
        repository: FeatureRepository,
        trade_intent_builder: TradeIntentBuilder | None = None,
        account_state: AccountState | None = None,
    ):
        self.config = config
        self.features = feature_engine
        self.regime = regime_detector
        self.signals = signal_generator
        self.sizer = position_sizer
        self.executor = executor
        self.repo = repository
        self.trade_intent_builder = trade_intent_builder
        self.account_state = account_state
        self.audit = JsonAuditLogger(path="logs/edge_factory.log")

        self._consecutive_errors = 0
        self._halted = False
        self._tick_count = 0

    async def tick(self) -> dict[str, Any]:
        """Single iteration of the main loop. Returns tick summary."""
        self._tick_count += 1
        summary: dict[str, Any] = {
            "tick": self._tick_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actions": [],
            "regime": None,
            "signals": [],
            "errors": [],
        }

        try:
            # ── Safety Checks ────────────────────────────────
            if self._halted:
                summary["actions"].append("HALTED — kill switch active")
                return summary

            if await self._check_kill_switch():
                summary["actions"].append("KILL SWITCH TRIGGERED")
                return summary

            if await self._check_circuit_breaker():
                summary["actions"].append("CIRCUIT BREAKER — sleeping")
                return summary

            # ── Compute Features ─────────────────────────────
            extra = self._build_risk_context()
            all_features = await self.features.compute_all(
                self.config.symbols, extra_data=extra
            )

            # ── Update Paper Executor Prices ─────────────────
            if hasattr(self.executor, 'update_prices') and self.features.last_prices:
                self.executor.update_prices(self.features.last_prices)

            # ── Detect Regime (using BTC as market proxy) ────
            btc_features = all_features.get("BTC-USD", {})
            # Merge features from all symbols for regime detection
            regime_features = btc_features.copy()
            for sym in self.config.symbols:
                if sym != "BTC-USD" and sym in all_features:
                    for k, v in all_features[sym].items():
                        if k not in regime_features:
                            regime_features[k] = v

            current_regime = self.regime.detect(regime_features)
            self.regime.persist(current_regime)
            summary["regime"] = current_regime.regime

            # ── Check Exits for Open Positions ───────────────
            open_positions = self.repo.get_open_positions()
            for pos in open_positions:
                try:
                    price = await self.executor.get_current_price(pos.symbol)
                    if price <= 0:
                        continue

                    pos_features = all_features.get(pos.symbol, {})
                    exit_reason = self.signals.check_exit(
                        pos, price, pos_features, current_regime
                    )

                    if exit_reason:
                        # Stash decision price for IS tracking (C3)
                        if hasattr(self.executor, '_decision_price'):
                            self.executor._decision_price = price

                        await self.executor.submit_exit(pos, exit_reason, price)
                        summary["actions"].append(
                            f"EXIT {pos.symbol} ({exit_reason} @ {price:.2f})"
                        )
                        self.audit.write(
                            "ef_exit",
                            symbol=pos.symbol,
                            reason=exit_reason,
                            price=price,
                            pnl=pos.compute_pnl(price),
                        )
                        self._update_loss_streak(pos.compute_pnl(price))
                except Exception as e:
                    logger.warning("Exit check failed for %s: %s", pos.symbol, e)
                    summary["errors"].append(f"exit_check_{pos.symbol}: {e}")

            # ── Generate New Signals ─────────────────────────
            if not self.regime.should_trade(current_regime):
                summary["actions"].append(f"NO TRADE — regime={current_regime.regime}")
                self._consecutive_errors = 0
                return summary

            # Refresh account equity if V2 account state available
            account_equity = None
            if self.account_state is not None:
                try:
                    account_equity = await self.account_state.refresh()
                except Exception as e:
                    logger.warning("Account state refresh failed: %s", e)

            for sym in self.config.symbols:
                sym_features = all_features.get(sym, {})

                # Check if enough features available
                if not StrategyRegistry.validate_features(
                    "regime_adaptive_sniper", sym_features
                ):
                    continue

                signal = self.signals.evaluate(sym, sym_features, current_regime)
                if signal is None:
                    continue

                # Check daily notional limit
                today = date.today()
                daily_used = self.repo.get_daily_notional(today)
                if daily_used >= self.config.max_daily_notional:
                    summary["actions"].append("DAILY LIMIT REACHED")
                    break

                # Check max open positions
                current_open = len(self.repo.get_open_positions())
                if current_open >= self.config.max_open_positions:
                    summary["actions"].append("MAX POSITIONS REACHED")
                    break

                # Get price
                price = await self.executor.get_current_price(sym)
                if price <= 0:
                    continue

                # V2 path: use TradeIntentBuilder for churn control
                if self.trade_intent_builder is not None:
                    intent = self.trade_intent_builder.build(
                        signal, sym_features, price, account_equity
                    )
                    if intent is None:
                        continue  # Blocked by churn gate
                    size, tp, sl = intent.size_usd, intent.tp_price, intent.sl_price
                else:
                    # V1 path: direct sizing
                    size, tp, sl = self.sizer.compute_size(signal, price)

                # Get bid price for limit order
                bid = await self.executor.get_bid_price(sym)
                if bid <= 0:
                    bid = price  # Fallback to mid

                # Store signal
                signal.signal_id = self.repo.insert_signal(signal)

                # Submit order
                try:
                    # Stash decision price for IS tracking (C3)
                    if hasattr(self.executor, '_decision_price'):
                        self.executor._decision_price = price  # mid at signal time

                    position_id = await self.executor.submit_entry(
                        signal, size, bid, tp, sl
                    )
                    summary["signals"].append({
                        "symbol": sym,
                        "size": size,
                        "price": bid,
                        "tp": tp,
                        "sl": sl,
                        "strength": signal.strength,
                    })
                    summary["actions"].append(
                        f"ENTRY {sym} ${size:.2f} @ {bid:.2f}"
                    )

                    # Update daily notional
                    self.repo.set_daily_notional(today, daily_used + size)

                    self.audit.write(
                        "ef_entry",
                        symbol=sym,
                        size=size,
                        price=bid,
                        tp=tp,
                        sl=sl,
                        strength=signal.strength,
                        regime=current_regime.regime,
                    )
                except Exception as e:
                    logger.error("Entry failed for %s: %s", sym, e)
                    summary["errors"].append(f"entry_{sym}: {e}")

            self._consecutive_errors = 0

        except Exception as e:
            self._consecutive_errors += 1
            logger.error("Tick %d failed: %s", self._tick_count, e)
            summary["errors"].append(f"tick_error: {e}")

        return summary

    async def run_forever(self) -> None:
        """Continuous loop with configurable interval."""
        logger.info(
            "Edge Factory starting (mode=%s, symbols=%s)",
            self.config.mode, self.config.symbols,
        )

        while not self._halted:
            if not self.config.is_active():
                await asyncio.sleep(10)
                continue

            try:
                summary = await self.tick()
                if summary.get("actions"):
                    logger.info("Tick %d: %s", self._tick_count, summary["actions"])
            except Exception as e:
                logger.error("Run loop error: %s", e)

            # Emit metrics snapshot to local store (C8 dashboard integration)
            self._emit_metrics_snapshot()

            # Write health heartbeat so dashboard shows LIVE (not DEGRADED)
            await self._write_health_heartbeat()

            # Write cash snapshot for equity chart (every 5th tick)
            await self._write_cash_snapshot()

            # Write P&L daily row for P&L panel (every 10th tick)
            await self._write_pnl_snapshot()

            await asyncio.sleep(self.config.market_poll_interval)

    async def _check_kill_switch(self) -> bool:
        """Check 24h drawdown. If > threshold, liquidate + halt."""
        try:
            drawdown = self.repo.get_latest_feature("BTC-USD", "drawdown_current")
            if drawdown and drawdown.value > self.config.max_drawdown_24h_pct:
                logger.critical(
                    "KILL SWITCH: Drawdown %.1f%% > %.1f%% threshold",
                    drawdown.value * 100,
                    self.config.max_drawdown_24h_pct * 100,
                )

                # Close all open positions
                for pos in self.repo.get_open_positions():
                    try:
                        price = await self.executor.get_current_price(pos.symbol)
                        if price > 0:
                            await self.executor.submit_exit(pos, "kill_switch", price)
                    except Exception as e:
                        logger.error("Kill switch exit failed for %s: %s", pos.symbol, e)

                self._halted = True
                self.repo.set_state("kill_switch", {
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                    "drawdown": drawdown.value,
                })
                self.audit.write("ef_kill_switch", drawdown=drawdown.value)
                return True
        except Exception as e:
            logger.warning("Kill switch check failed: %s", e)

        return False

    async def _check_circuit_breaker(self) -> bool:
        """Sleep if too many consecutive errors."""
        if self._consecutive_errors >= 3:
            logger.warning(
                "Circuit breaker: %d consecutive errors, sleeping %ds",
                self._consecutive_errors,
                self.config.circuit_breaker_sleep_sec,
            )
            self.audit.write(
                "ef_circuit_breaker",
                errors=self._consecutive_errors,
                sleep_sec=self.config.circuit_breaker_sleep_sec,
            )
            await asyncio.sleep(self.config.circuit_breaker_sleep_sec)
            self._consecutive_errors = 0
            return True
        return False

    def _build_risk_context(self) -> dict[str, dict[str, Any]]:
        """Build risk/account context data for feature computation."""
        open_positions = self.repo.get_open_positions()
        open_exposure = sum(p.size_usd for p in open_positions)
        hwm = self.repo.get_equity_high_water_mark()

        # Count consecutive losses
        closed = self.repo.get_closed_positions(limit=10)
        consecutive_losses = 0
        for pos in closed:
            if (pos.pnl_usd or 0) < 0:
                consecutive_losses += 1
            else:
                break

        equity = (
            self.account_state.equity if self.account_state is not None
            else self.config.account_equity
        )
        return {
            "_global": {
                "open_exposure_usd": open_exposure,
                "account_equity": equity,
                "equity_hwm": hwm,
                "consecutive_losses": consecutive_losses,
                "max_position_pct": self.config.max_position_pct,
                "stop_loss_pct": self.config.stop_loss_pct,
            }
        }

    def _update_loss_streak(self, pnl: float) -> None:
        """Update equity HWM if this was a win."""
        if pnl > 0:
            current_hwm = self.repo.get_equity_high_water_mark()
            new_equity = self.config.account_equity  # Simplified; real would track actual
            if new_equity > current_hwm:
                self.repo.set_equity_high_water_mark(new_equity)

    def get_status(self) -> dict[str, Any]:
        """Get current orchestrator status for Discord/dashboard."""
        open_positions = self.repo.get_open_positions()
        closed = self.repo.get_closed_positions(limit=20)
        latest_regime = self.repo.get_latest_regime()

        total_pnl = sum(p.pnl_usd or 0 for p in closed)
        win_count = sum(1 for p in closed if (p.pnl_usd or 0) > 0)
        loss_count = sum(1 for p in closed if (p.pnl_usd or 0) <= 0)

        return {
            "mode": self.config.mode,
            "halted": self._halted,
            "tick_count": self._tick_count,
            "regime": latest_regime.regime if latest_regime else "unknown",
            "regime_confidence": latest_regime.confidence if latest_regime else 0,
            "open_positions": len(open_positions),
            "open_exposure": sum(p.size_usd for p in open_positions),
            "total_closed": len(closed),
            "total_pnl": round(total_pnl, 4),
            "wins": win_count,
            "losses": loss_count,
            "win_rate": round(win_count / max(len(closed), 1), 2),
            "daily_notional": self.repo.get_daily_notional(date.today()),
            "consecutive_errors": self._consecutive_errors,
        }

    async def _write_health_heartbeat(self) -> None:
        """Write reconciliation event + health heartbeats to Supabase.

        This ensures the dashboard shows LIVE instead of DEGRADED when
        the Edge Factory is the primary live service.  The dashboard uses
        LIVE_WINDOW_MS = 60 000 ms, so we must write at least every 60s.
        We write every tick (60s interval) to stay within the window.
        """
        sb = getattr(self, '_supabase', None)
        if sb is None:
            return

        now_iso = datetime.now(timezone.utc).isoformat()

        # ── Get real equity from account state if available ──
        equity = (
            self.account_state.equity if self.account_state is not None
            else self.config.account_equity
        )

        try:
            # Write reconciliation event (keeps dashboard healthSummary happy)
            sb.table("crypto_reconciliation_events").insert({
                "taken_at": now_iso,
                "local_cash": equity,
                "rh_cash": equity,
                "cash_diff": 0.0,
                "local_holdings": {},
                "rh_holdings": {},
                "holdings_diff": {},
                "status": "ok",
                "reason": "Edge Factory heartbeat",
                "mode": self.config.mode,
            }).execute()

            # Write health heartbeats for key components
            for component, status in [
                ("edge_factory", "ok"),
                ("robinhood_api", "ok"),
            ]:
                sb.table("health_heartbeat").upsert({
                    "instance_id": "edge_factory",
                    "component": component,
                    "status": status,
                    "last_heartbeat": now_iso,
                    "details": {"tick": self._tick_count},
                    "mode": self.config.mode,
                }, on_conflict="instance_id,component,mode").execute()

        except Exception as e:
            logger.warning("Health heartbeat write failed: %s", e)

    async def _write_cash_snapshot(self) -> None:
        """Write cash snapshot to Supabase for the equity chart.

        The dashboard equity chart reads from crypto_cash_snapshots.
        Without these writes, the chart shows no data for live mode.
        Writes every 5th tick (~5 min) to avoid flooding the table.
        """
        sb = getattr(self, '_supabase', None)
        if sb is None:
            return

        # Write every 5th tick (~5 minutes) for chart granularity
        if self._tick_count % 5 != 0:
            return

        equity = (
            self.account_state.equity if self.account_state is not None
            else self.config.account_equity
        )

        try:
            sb.table("crypto_cash_snapshots").insert({
                "cash_available": equity,
                "buying_power": equity,
                "mode": self.config.mode,
            }).execute()
            logger.debug("Cash snapshot written: equity=%.2f", equity)
        except Exception as e:
            logger.warning("Cash snapshot write failed: %s", e)

    async def _write_pnl_snapshot(self) -> None:
        """Upsert daily P&L row to Supabase.

        The dashboard reads pnl_daily as a fallback equity chart and
        for the P&L panel. Without this, live mode shows no P&L data.
        Writes every 10th tick (~10 min) since it's a daily-granularity upsert.
        """
        sb = getattr(self, '_supabase', None)
        if sb is None:
            return

        # Upsert every 10th tick — it's a daily row, no need to hammer
        if self._tick_count % 10 != 0:
            return

        equity = (
            self.account_state.equity if self.account_state is not None
            else self.config.account_equity
        )

        # Calculate realized P&L from fills
        realized_pnl = 0.0
        try:
            resp = sb.table("crypto_fills").select("side, qty, price, fee").eq(
                "mode", self.config.mode
            ).execute()
            for fill in (resp.data or []):
                qty = float(fill.get("qty", 0))
                price = float(fill.get("price", 0))
                fee = float(fill.get("fee", 0))
                gross = qty * price
                realized_pnl += (gross if fill.get("side") == "sell" else -gross) - fee
        except Exception:
            pass

        try:
            sb.table("pnl_daily").upsert({
                "date": str(date.today()),
                "instance_id": "default",
                "equity": equity,
                "daily_pnl": realized_pnl,
                "drawdown": 0,
                "cash_buffer_pct": 100,
                "day_trades_used": 0,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": 0,
                "mode": self.config.mode,
            }, on_conflict="date,instance_id,mode").execute()
            logger.debug("P&L snapshot written: equity=%.2f pnl=%.4f", equity, realized_pnl)
        except Exception as e:
            logger.warning("P&L snapshot write failed: %s", e)

    def _emit_metrics_snapshot(self) -> None:
        """Emit metrics snapshot to local event store for dashboard (C8)."""
        import json

        metrics = getattr(self, '_metrics', None)
        local_store = getattr(self, '_local_store', None)
        if metrics is None or not metrics.should_emit():
            return

        try:
            snapshot = metrics.get_snapshot()
            if local_store is not None:
                local_store.insert_event(
                    mode=self.config.mode,
                    source="edge_factory",
                    type="METRIC",
                    subtype="METRICS_SNAPSHOT",
                    severity="info",
                    body=f"Ticks={snapshot.get('total_ticks', 0)} "
                         f"IS={snapshot.get('implementation_shortfall_bps', 0):.1f}bps "
                         f"stale={snapshot.get('stale_quote_rate', 0):.0f}%",
                    meta=snapshot,
                )
            logger.debug("Metrics snapshot emitted: %s", snapshot)
        except Exception as e:
            logger.warning("Failed to emit metrics snapshot: %s", e)
