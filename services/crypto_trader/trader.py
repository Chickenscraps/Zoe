from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from .broker import Broker
from .candle_manager import CandleManager
from .config import CONFIRM_PHRASE, CryptoTraderConfig
from .logger import JsonAuditLogger
from .price_cache import PriceCache
from .repository import CryptoRepository
from .scanner import scan_candidates
from .signals import generate_signals, Signal
from .exit_manager import SmartExitManager, ExitConfig, ExitReason, ExitUrgency
from .consensus import ConsensusEngine

logger = logging.getLogger(__name__)


@dataclass
class HealthState:
    status: str
    reason: str
    last_reconcile_at: str | None
    daily_notional_used: float
    live_enabled: bool
    open_orders: int


class CryptoTraderService:
    """Main trading loop — broker-agnostic.

    Supports three broker backends (paper / robinhood / kraken) and two
    market-data sources (polling / kraken_ws), selectable via config flags.
    """

    def __init__(
        self,
        broker: Broker,
        repository: CryptoRepository,
        config: CryptoTraderConfig | None = None,
        *,
        # Optional Kraken components — injected by the startup harness
        market_data_service: Any | None = None,
        order_executor: Any | None = None,
        fill_processor: Any | None = None,
        pnl_service: Any | None = None,
        repositioner: Any | None = None,
        circuit_breaker: Any | None = None,
        ws_private: Any | None = None,
        ws_manager: Any | None = None,
        # Legacy compatibility: raw RH client for polling path
        rh_client: Any | None = None,
    ):
        self.broker = broker
        self.repo = repository
        self.cfg = config or CryptoTraderConfig()
        self.mode = self.cfg.mode
        self.audit = JsonAuditLogger()
        self.price_cache = PriceCache(capacity_per_symbol=288)  # 24h at 5-min ticks
        self.candle_manager = CandleManager()
        self.price_cache.set_candle_manager(self.candle_manager)  # Wire candle ingestion
        self.exit_manager = SmartExitManager(
            price_cache=self.price_cache,
            consensus_engine=ConsensusEngine(),
            config=ExitConfig(),
        )
        self._paused = False
        self._degraded = False
        self._last_reconcile_at: str | None = None
        self._safe_mode_until: float = 0.0
        self._cycle_count: int = 0
        self._next_historical_refresh: float = 0.0

        # ── New Kraken components (None if not using Kraken) ──
        self.market_data = market_data_service
        self.order_executor = order_executor
        self.fill_processor = fill_processor
        self.pnl_service = pnl_service
        self.repositioner = repositioner
        self.circuit_breaker = circuit_breaker
        self.ws_private = ws_private
        self.ws_manager = ws_manager

        # Legacy RH client for polling path (when market_data_source=polling)
        self._rh_client = rh_client

        # Background tasks (WS loops, etc.)
        self._background_tasks: list[asyncio.Task] = []

    # ── Admin controls ──

    def _require_admin(self, initiator_id: str) -> None:
        if initiator_id != self.cfg.admin_user_id:
            raise PermissionError("Crypto controls are admin-only.")

    def set_live(self, initiator_id: str, enabled: bool, confirmation: str = "") -> str:
        self._require_admin(initiator_id)
        if enabled and confirmation != CONFIRM_PHRASE:
            raise ValueError("Live mode denied: missing exact confirmation phrase")
        self.cfg.rh_live_trading = enabled
        self.cfg.rh_live_confirm = confirmation if enabled else ""
        self.audit.write("crypto_live_mode", enabled=enabled)
        return "LIVE ON" if enabled else "LIVE OFF"

    def pause(self, initiator_id: str) -> str:
        self._require_admin(initiator_id)
        self._paused = True
        self.audit.write("crypto_pause", by=initiator_id)
        return "Crypto trading paused"

    def resume(self, initiator_id: str) -> str:
        self._require_admin(initiator_id)
        self._paused = False
        self.audit.write("crypto_resume", by=initiator_id)
        return "Crypto trading resumed"

    def _validate_symbol(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        # Accept both dash-separated (BTC-USD) and slash-separated (BTC/USD)
        if normalized.endswith("-USD") or normalized.endswith("/USD"):
            return normalized
        if normalized.endswith("-USDT") or normalized.endswith("/USDT"):
            return normalized
        if normalized.endswith("-USDC") or normalized.endswith("/USDC"):
            return normalized
        raise ValueError(f"Only USD/USDT/USDC quoted pairs are allowed, got: {symbol}")

    def _enforce_trade_limits(self, *, notional: float, symbol: str) -> None:
        if notional > self.cfg.max_notional_per_trade:
            raise ValueError("Trade blocked by MAX_NOTIONAL_PER_TRADE")
        today = date.today()
        used = self.repo.get_daily_notional(today, self.mode)
        if used + notional > self.cfg.max_daily_notional:
            raise ValueError("Trade blocked by MAX_DAILY_NOTIONAL")
        holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
        open_positions = [asset for asset, qty in holdings.items() if float(qty) > 0]
        if symbol not in open_positions and len(open_positions) >= self.cfg.max_open_positions:
            raise ValueError("Trade blocked by MAX_OPEN_POSITIONS")

    # ── Order placement ──

    async def place_order(self, *, initiator_id: str, symbol: str, side: str, notional: float | None = None, qty: float | None = None, order_type: str = "market", limit_price: float | None = None) -> dict[str, Any]:
        self._require_admin(initiator_id)
        if self._paused:
            raise RuntimeError("Trading paused")
        if self._degraded and self.cfg.stop_trading_on_degraded:
            raise RuntimeError("Trading frozen while DEGRADED")
        if not self.cfg.live_ready():
            raise RuntimeError("Live trading disabled (feature flag / confirmation not satisfied)")
        if time.time() < self._safe_mode_until:
            raise RuntimeError("Trading blocked: boot safe-mode cooldown active")

        # Circuit breaker guard
        if self.circuit_breaker and self.circuit_breaker.is_open:
            raise RuntimeError("Trading blocked: circuit breaker OPEN (stale market data)")

        safe_symbol = self._validate_symbol(symbol)
        order_notional = notional or ((qty or 0) * (limit_price or 0))
        self._enforce_trade_limits(notional=order_notional, symbol=safe_symbol)

        client_order_id = f"zoe-{safe_symbol.lower().replace('/', '-')}-{uuid.uuid4()}"

        # Use OrderExecutor if available (Kraken path), otherwise direct broker call
        if self.order_executor and qty:
            result = await self.order_executor.submit_order(
                symbol=safe_symbol,
                side=side,
                qty=qty,
                limit_price=limit_price,
                order_type=order_type,
                strategy="manual",
                reason="manual_order",
            )
        else:
            # Legacy path: direct broker call (RH or PaperBroker)
            result = await self.broker.place_order(
                symbol=safe_symbol,
                side=side,
                qty=qty or 0,
                limit_price=limit_price or 0,
                order_type=order_type,
                client_order_id=client_order_id,
            )
            self.repo.insert_order(
                {
                    "id": result.get("id", client_order_id),
                    "client_order_id": client_order_id,
                    "symbol": safe_symbol,
                    "side": side,
                    "order_type": order_type,
                    "qty": qty,
                    "notional": notional,
                    "status": result.get("status", "submitted"),
                    "raw_response": result,
                    "mode": self.mode,
                }
            )

        self.repo.set_daily_notional(date.today(), self.repo.get_daily_notional(date.today(), self.mode) + order_notional, self.mode)
        self.audit.write("crypto_order_submitted", symbol=safe_symbol, side=side, notional=order_notional, client_order_id=client_order_id, mode=self.mode)
        return result

    def _compute_local_ledger(self) -> tuple[float, dict[str, float]]:
        start_cash = float((self.repo.latest_cash_snapshot(self.mode) or {}).get("cash_available", 0.0))
        local_cash = start_cash
        holdings: dict[str, float] = {}
        for fill in getattr(self.repo, "fills", []):
            qty = float(fill.get("qty", 0))
            px = float(fill.get("price", 0))
            fee = float(fill.get("fee", 0))
            symbol = fill.get("symbol")
            side = fill.get("side")
            delta = qty if side == "buy" else -qty
            holdings[symbol] = holdings.get(symbol, 0.0) + delta
            cash_delta = -(qty * px + fee) if side == "buy" else (qty * px - fee)
            local_cash += cash_delta
        return local_cash, holdings

    # ── Reconciliation ──

    async def reconcile(self) -> HealthState:
        if self.mode == "paper":
            return await self._reconcile_paper()
        return await self._reconcile_live()

    async def _reconcile_paper(self) -> HealthState:
        """Paper mode: use broker-reported state."""
        cash = await self.broker.get_cash()
        positions = await self.broker.get_positions()

        # If no fills yet, use starting equity from config
        if cash == 0.0 and not positions:
            cash = float(getattr(self.cfg, "starting_equity", 2000.0))

        total_value = 0.0

        # If we have market data, compute total value
        if self.market_data:
            for sym, qty in positions.items():
                snap = self.market_data.get_focus_snapshot(sym)
                if snap and snap.mid > 0:
                    total_value += qty * snap.mid

        self.repo.insert_cash_snapshot(cash_available=cash, buying_power=cash, mode=self.mode)
        self.repo.insert_holdings_snapshot(holdings=positions, total_value=total_value, mode=self.mode)
        self.repo.insert_reconciliation_event(
            {
                "taken_at": datetime.now(timezone.utc).isoformat(),
                "local_cash": cash,
                "broker_cash": cash,
                "cash_diff": 0.0,
                "local_holdings": positions,
                "broker_holdings": positions,
                "status": "ok",
                "reason": "paper mode - broker ledger",
                "mode": self.mode,
            }
        )
        notional = self.repo.get_daily_notional(date.today(), self.mode)
        return HealthState(
            status="ok",
            reason="paper mode",
            last_reconcile_at=datetime.now(timezone.utc).isoformat(),
            daily_notional_used=notional,
            live_enabled=False,
            open_orders=0,
        )

    async def _reconcile_live(self) -> HealthState:
        """Live mode: reconcile against real broker API."""
        broker_cash = await self.broker.get_cash()
        broker_positions = await self.broker.get_positions()
        broker_buying_power = broker_cash

        # Compute total value using market data
        total_value = 0.0
        if self.market_data:
            for sym, qty in broker_positions.items():
                snap = self.market_data.get_focus_snapshot(sym)
                if snap and snap.mid > 0:
                    total_value += qty * snap.mid

        local_cash, local_holdings = self._compute_local_ledger()
        cash_diff = local_cash - broker_cash
        holding_diff = {
            sym: local_holdings.get(sym, 0.0) - broker_positions.get(sym, 0.0)
            for sym in sorted(set(local_holdings) | set(broker_positions))
            if abs(local_holdings.get(sym, 0.0) - broker_positions.get(sym, 0.0)) > 0.0000001
        }

        status = "ok"
        reason = ""
        if abs(cash_diff) > 1 or holding_diff:
            status = "degraded"
            reason = "Mismatch between local ledger and broker snapshots"

        self.repo.insert_cash_snapshot(cash_available=broker_cash, buying_power=broker_buying_power, mode=self.mode)
        self.repo.insert_holdings_snapshot(holdings=broker_positions, total_value=total_value, mode=self.mode)
        self.repo.insert_reconciliation_event(
            {
                "taken_at": datetime.now(timezone.utc).isoformat(),
                "local_cash": local_cash,
                "broker_cash": broker_cash,
                "cash_diff": cash_diff,
                "local_holdings": local_holdings,
                "broker_holdings": broker_positions,
                "holdings_diff": holding_diff,
                "status": status,
                "reason": reason,
                "mode": self.mode,
            }
        )

        self._degraded = status == "degraded"
        self._last_reconcile_at = datetime.now(timezone.utc).isoformat()
        self.audit.write("crypto_reconcile", status=status, reason=reason, cash_diff=cash_diff, holdings_diff=holding_diff)

        if self._degraded and self.cfg.stop_trading_on_degraded:
            self.audit.write("crypto_trading_frozen", reason="stop_trading_on_degraded")

        return self.get_health(reason_override=reason)

    # ── Order polling ──

    async def poll_open_orders(self) -> None:
        """Poll open orders for status updates.

        When using Kraken WS private feed, fills arrive via WS callbacks
        and this method only does REST-based reconciliation as fallback.
        """
        if self.cfg.broker_type == "kraken" and self.ws_private and self.ws_private.connected:
            # WS-driven fill processing is active — only do lightweight REST check
            await self._poll_open_orders_broker()
            return

        if self._rh_client:
            # Legacy RH polling path
            await self._poll_open_orders_rh()
            return

        # Generic broker path
        await self._poll_open_orders_broker()

    async def _poll_open_orders_rh(self) -> None:
        """Legacy Robinhood order polling via RH client."""
        from integrations.robinhood_crypto_client.client import _sanitize
        for order in self.repo.list_open_orders(self.mode):
            rh_order = await self._rh_client.get_order(order["id"])
            status = rh_order.get("status", order.get("status", "submitted"))
            self.repo.update_order_status(order["id"], status, _sanitize(rh_order))

            fills = await self._rh_client.get_order_fills(order["id"])
            for fill in fills.get("results", fills if isinstance(fills, list) else []):
                self.repo.upsert_fill(
                    {
                        "order_id": order["id"],
                        "fill_id": fill.get("id"),
                        "symbol": order.get("symbol"),
                        "side": order.get("side"),
                        "qty": float(fill.get("quantity", 0)),
                        "price": float(fill.get("price", 0)),
                        "fee": float(fill.get("fee", 0)),
                        "executed_at": fill.get("executed_at"),
                        "mode": self.mode,
                    }
                )
            if status in {"partially_filled", "filled", "canceled", "rejected"}:
                await self.reconcile()

    async def _poll_open_orders_broker(self) -> None:
        """Generic broker-based order polling (Kraken + Paper)."""
        for order in self.repo.list_open_orders(self.mode):
            order_id = order.get("id", "")
            try:
                fills = await self.broker.get_fills(order_id)
                for fill in fills:
                    self.repo.upsert_fill(
                        {
                            "order_id": order_id,
                            "fill_id": fill.get("fill_id", fill.get("id", "")),
                            "symbol": order.get("symbol"),
                            "side": order.get("side"),
                            "qty": float(fill.get("qty", 0)),
                            "price": float(fill.get("price", 0)),
                            "fee": float(fill.get("fee", 0)),
                            "fee_currency": fill.get("fee_currency", "USD"),
                            "executed_at": fill.get("executed_at"),
                            "mode": self.mode,
                        }
                    )
                # Check if order should be marked as terminal
                broker_orders = await self.broker.get_open_orders()
                broker_order_ids = {o.get("id", o.get("order_id", "")) for o in broker_orders}
                if order_id not in broker_order_ids:
                    current_status = order.get("status", "submitted")
                    if current_status in ("submitted", "open", "partially_filled"):
                        self.repo.update_order_status(order_id, "filled", {})
            except NotImplementedError:
                pass  # broker doesn't support get_fills; skip

    def get_health(self, reason_override: str = "") -> HealthState:
        daily_notional = self.repo.get_daily_notional(date.today(), self.mode)
        status = "DEGRADED" if self._degraded else "LIVE"
        if self.circuit_breaker and self.circuit_breaker.is_open:
            status = "CIRCUIT_OPEN"
        return HealthState(
            status=status,
            reason=reason_override,
            last_reconcile_at=self._last_reconcile_at,
            daily_notional_used=daily_notional,
            live_enabled=self.cfg.live_ready(),
            open_orders=len(self.repo.list_open_orders(self.mode)),
        )

    async def run_once(self) -> None:
        await self.poll_open_orders()
        await self.reconcile()

    # ── Heartbeats & PnL ──

    def _write_heartbeats(self, health: HealthState) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        broker_name = self.cfg.broker_type
        components = [
            (f"{broker_name}_api", "ok" if not self._degraded else "warning"),
            ("reconciliation_engine", "ok" if health.status not in ("DEGRADED", "CIRCUIT_OPEN") else "warning"),
            ("snapshot_store", "ok"),
            ("discord_control", "ok"),
        ]
        # Add WS-specific heartbeats when using Kraken
        if self.ws_manager:
            ws_status = "ok" if self.ws_manager.connected else "error"
            components.append(("kraken_ws_public", ws_status))
        if self.ws_private:
            ws_status = "ok" if self.ws_private.connected else "error"
            components.append(("kraken_ws_private", ws_status))
        if self.circuit_breaker:
            cb_status = "ok" if self.circuit_breaker.allows_trading else "warning"
            components.append(("circuit_breaker", cb_status))

        for component, status in components:
            try:
                self.repo.upsert_health_heartbeat({
                    "instance_id": "default",
                    "component": component,
                    "status": status,
                    "last_heartbeat": now_iso,
                    "details": {"reason": health.reason} if health.reason else {},
                    "mode": self.mode,
                })
            except Exception:
                pass

    def _write_pnl_snapshot(self, equity: float) -> None:
        """Write P&L snapshot — uses PnlService when available."""
        if self.pnl_service and self.market_data:
            try:
                focus_prices = {
                    s.symbol: s.mid
                    for s in self.market_data.get_all_focus_snapshots().values()
                    if s.mid > 0
                }
                self.pnl_service.compute_and_write(equity, focus_prices)
                return
            except Exception as e:
                logger.warning("PnlService snapshot failed, falling back: %s", e)

        # Fallback: simple PnL write (legacy path)
        realized = self.repo.get_realized_pnl(self.mode)
        try:
            self.repo.upsert_pnl_daily({
                "date": str(date.today()),
                "instance_id": "default",
                "equity": equity,
                "daily_pnl": realized,
                "drawdown": 0,
                "cash_buffer_pct": 100,
                "day_trades_used": 0,
                "realized_pnl": realized,
                "unrealized_pnl": 0,
                "mode": self.mode,
            })
        except Exception as e:
            print(f"[ZOE] pnl_daily write error: {e}")

    def _write_thought(self, content: str, thought_type: str = "general", symbol: str | None = None, metadata: dict | None = None) -> None:
        try:
            row: dict[str, Any] = {
                "instance_id": "default",
                "content": content,
                "type": thought_type,
                "mode": self.mode,
            }
            if symbol:
                row["symbol"] = symbol
            if metadata:
                row["metadata"] = metadata
            self.repo.insert_thought(row)
        except Exception:
            pass

    # ── Positions ──

    def _get_open_positions(self) -> set[str]:
        """Get set of symbols with open positions."""
        holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
        return {sym for sym, qty in holdings.items() if float(qty) > 0}

    # ── Scan / Signal pipeline ──

    async def _run_scan(self) -> None:
        """Full pipeline: scan -> score -> signal -> (optional) auto-execute."""
        try:
            # Phase 1: Scan — fetch prices, update cache, score (with chart analysis)
            if self._rh_client:
                candidates = await scan_candidates(self._rh_client, self.price_cache, self.candle_manager)
            else:
                candidates = await scan_candidates(None, self.price_cache, self.candle_manager)
            if not candidates:
                return

            # Persist scan results to dashboard
            rows = [
                {
                    "instance_id": "default",
                    "symbol": c.symbol,
                    "score": c.score,
                    "score_breakdown": c.score_breakdown,
                    "info": c.info,
                    "recommended_strategy": c.recommended_strategy,
                    "mode": self.mode,
                }
                for c in candidates
            ]
            self.repo.upsert_candidate_scans(rows)

            top = candidates[0]
            tick_counts = {c.symbol: c.info.get("tick_count", 0) for c in candidates[:3]}
            print(f"[ZOE] Scan: {len(candidates)} symbols | top={top.symbol} ({top.score}) | ticks={tick_counts}")

            # Phase 2: Generate signals
            open_positions = self._get_open_positions()
            signals = generate_signals(
                candidates=candidates,
                price_cache=self.price_cache,
                open_positions=open_positions,
                max_notional=self.cfg.max_notional_per_trade,
                max_signals=self.cfg.max_open_positions,
            )

            actionable = [s for s in signals if s.is_actionable]
            holds = [s for s in signals if not s.is_actionable]

            # Log scan thought
            scan_summary = f"Scanned {len(candidates)} symbols. Top: {top.symbol} (score {top.score:.0f})"
            if actionable:
                action_strs = [f"{s.action} {s.symbol} ({s.confidence:.0%})" for s in actionable]
                scan_summary += f" | Signals: {', '.join(action_strs)}"
            else:
                scan_summary += " | No actionable signals"

            self._write_thought(
                scan_summary,
                thought_type="scan",
                symbol=top.symbol,
                metadata={
                    "count": len(candidates),
                    "top_score": top.score,
                    "actionable_signals": len(actionable),
                    "signals": [s.to_dict() for s in actionable],
                },
            )

            # Phase 3: Auto-execute actionable signals
            for signal in actionable:
                await self._execute_signal(signal)

        except Exception as e:
            import traceback
            print(f"[ZOE] Scan pipeline error: {e}")
            traceback.print_exc()

    async def _execute_signal(self, signal: Signal) -> None:
        """Execute a single signal — place order if all checks pass."""
        sym = signal.symbol
        action = signal.action
        notional = signal.suggested_notional

        # Guard checks
        if self._paused:
            self._write_thought(f"Signal {action} {sym} skipped -- trading paused", thought_type="signal", symbol=sym)
            return
        if time.time() < self._safe_mode_until:
            self._write_thought(f"Signal {action} {sym} skipped -- safe mode cooldown", thought_type="signal", symbol=sym)
            return
        if self._degraded and self.cfg.stop_trading_on_degraded:
            self._write_thought(f"Signal {action} {sym} skipped -- degraded state", thought_type="signal", symbol=sym)
            return
        if self.circuit_breaker and self.circuit_breaker.is_open:
            self._write_thought(f"Signal {action} {sym} skipped -- circuit breaker OPEN", thought_type="signal", symbol=sym)
            return
        if notional <= 0:
            return
        if notional < self.cfg.min_notional_per_trade:
            self._write_thought(
                f"Signal {action} {sym} skipped -- notional ${notional:.2f} below ${self.cfg.min_notional_per_trade:.0f} minimum",
                thought_type="signal", symbol=sym,
            )
            return

        side = "buy" if action == "BUY" else "sell"

        # Log the decision
        self._write_thought(
            f"Executing {action} {sym}: ${notional:.2f} notional | confidence={signal.confidence:.0%} | {signal.reason}",
            thought_type="signal",
            symbol=sym,
            metadata=signal.to_dict(),
        )
        self.audit.write(
            "crypto_signal_execute",
            symbol=sym,
            action=action,
            confidence=signal.confidence,
            notional=notional,
            reason=signal.reason,
            strategy=signal.strategy,
            mode=self.mode,
        )
        print(f"[ZOE] SIGNAL: {action} {sym} ${notional:.2f} (conf={signal.confidence:.0%}) -- {signal.reason}")

        # Only place real orders if live_ready
        if not self.cfg.live_ready():
            # Paper mode: log as paper trade thought
            self._write_thought(
                f"PAPER {action} {sym}: ${notional:.2f} (would execute if live)",
                thought_type="paper_trade",
                symbol=sym,
                metadata=signal.to_dict(),
            )
            print(f"[ZOE] PAPER TRADE: {action} {sym} ${notional:.2f}")

            # Register with exit manager so exits are tracked even in paper mode
            if action == "BUY":
                snap = self.price_cache.snapshot(sym)
                entry_price = snap.get("mid", 0)
                if entry_price > 0:
                    self.exit_manager.register_position(
                        symbol=sym,
                        entry_price=entry_price,
                        entry_time=datetime.now(timezone.utc),
                    )
            return

        # Live execution
        try:
            # Compute qty from notional using current mid price
            mid_price = 0.0
            if self.market_data:
                focus_snap = self.market_data.get_focus_snapshot(sym)
                if focus_snap and focus_snap.mid > 0:
                    mid_price = focus_snap.mid
            if mid_price == 0:
                snap = self.price_cache.snapshot(sym)
                mid_price = snap.get("mid", 0)
            if mid_price <= 0:
                self._write_thought(f"Signal {action} {sym} skipped -- no price available", thought_type="signal", symbol=sym)
                return

            qty = notional / mid_price

            if self.order_executor:
                # Kraken path: use intent-based executor
                result = await self.order_executor.submit_order(
                    symbol=sym,
                    side=side,
                    qty=qty,
                    limit_price=mid_price,  # limit order at mid
                    order_type="limit",
                    strategy=signal.strategy,
                    reason=signal.reason,
                )
            else:
                # Legacy path: direct place_order
                result = await self.place_order(
                    initiator_id=self.cfg.admin_user_id,
                    symbol=sym,
                    side=side,
                    qty=qty,
                    order_type="market",
                )

            self._write_thought(
                f"Order placed: {action} {sym} ${notional:.2f} -> {result.get('status', 'submitted')}",
                thought_type="order",
                symbol=sym,
                metadata={"order_id": result.get("id"), "signal": signal.to_dict()},
            )

            # Register with exit manager on live BUY
            if action == "BUY":
                self.exit_manager.register_position(
                    symbol=sym,
                    entry_price=mid_price,
                    entry_time=datetime.now(timezone.utc),
                )
        except Exception as e:
            self._write_thought(
                f"Order FAILED: {action} {sym} ${notional:.2f} -- {e}",
                thought_type="order_error",
                symbol=sym,
                metadata={"error": str(e), "signal": signal.to_dict()},
            )
            print(f"[ZOE] ORDER FAILED for {sym}: {e}")

    # ── Exit management ──

    async def _check_exits(self) -> None:
        """Check all open positions against exit rules every tick."""
        try:
            holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
            open_symbols = {sym for sym, qty in holdings.items() if float(qty) > 0}

            # Register any positions the exit manager doesn't know about
            for sym in open_symbols:
                if self.exit_manager.get_position_state(sym) is None:
                    snap = self.price_cache.snapshot(sym)
                    mid = snap.get("mid", 0)
                    self.exit_manager.register_position(
                        symbol=sym,
                        entry_price=mid,
                        entry_time=datetime.now(timezone.utc),
                    )

            # Unregister positions that are no longer held
            for sym in list(self.exit_manager.active_positions()):
                if sym not in open_symbols:
                    self.exit_manager.unregister_position(sym)

            # Check each position for exit conditions
            for sym in open_symbols:
                snap = self.price_cache.snapshot(sym)
                current_price = snap.get("mid", 0)
                current_spread = snap.get("spread_pct", 0)

                if current_price <= 0:
                    continue

                exit_signal = self.exit_manager.check_exits(
                    symbol=sym,
                    current_price=current_price,
                    current_spread_pct=current_spread,
                )

                if exit_signal is not None:
                    await self._execute_exit(sym, exit_signal)

        except Exception as e:
            import traceback
            print(f"[ZOE] Exit check error: {e}")
            traceback.print_exc()

    async def _execute_exit(self, symbol: str, exit_signal: 'ExitSignal') -> None:
        """Execute an exit signal — sell the position."""
        self._write_thought(
            f"EXIT {symbol}: {exit_signal.reason.value} | {exit_signal.details} | P&L: {exit_signal.pnl_pct:.2%}",
            thought_type="exit_signal",
            symbol=symbol,
            metadata=exit_signal.to_dict(),
        )
        self.audit.write(
            "crypto_exit_signal",
            symbol=symbol,
            reason=exit_signal.reason.value,
            urgency=exit_signal.urgency.value,
            pnl_pct=exit_signal.pnl_pct,
            details=exit_signal.details,
            mode=self.mode,
        )
        print(f"[ZOE] EXIT: {exit_signal.reason.value} {symbol} ({exit_signal.pnl_pct:.2%}) -- {exit_signal.details}")

        if not self.cfg.live_ready():
            self._write_thought(
                f"PAPER EXIT {symbol}: {exit_signal.reason.value} (would sell if live)",
                thought_type="paper_exit",
                symbol=symbol,
                metadata=exit_signal.to_dict(),
            )
            print(f"[ZOE] PAPER EXIT: {symbol} {exit_signal.reason.value}")
            self.exit_manager.unregister_position(symbol)
            return

        # Live execution: sell the position
        try:
            holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
            qty = float(holdings.get(symbol, 0))
            if qty <= 0:
                self.exit_manager.unregister_position(symbol)
                return

            if self.order_executor:
                result = await self.order_executor.submit_order(
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    order_type="market",
                    strategy="exit",
                    reason=exit_signal.reason.value,
                )
            else:
                result = await self.place_order(
                    initiator_id=self.cfg.admin_user_id,
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    order_type="market",
                )

            self._write_thought(
                f"Exit order placed: SELL {symbol} qty={qty} -> {result.get('status', 'submitted')} | reason={exit_signal.reason.value}",
                thought_type="exit_order",
                symbol=symbol,
                metadata={"order_id": result.get("id"), "exit": exit_signal.to_dict()},
            )
            self.exit_manager.unregister_position(symbol)
        except Exception as e:
            self._write_thought(
                f"Exit order FAILED: SELL {symbol} -- {e}",
                thought_type="exit_error",
                symbol=symbol,
                metadata={"error": str(e), "exit": exit_signal.to_dict()},
            )
            print(f"[ZOE] EXIT ORDER FAILED for {symbol}: {e}")

    # ── Agent state ──

    def _save_agent_state_snapshot(self) -> None:
        try:
            holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
            cash_snap = self.repo.latest_cash_snapshot(self.mode) or {}
            state: dict[str, Any] = {
                "open_orders": [o["id"] for o in self.repo.list_open_orders(self.mode)],
                "holdings": holdings,
                "cash_available": cash_snap.get("cash_available", 0),
                "buying_power": cash_snap.get("buying_power", 0),
                "daily_notional_used": self.repo.get_daily_notional(date.today(), self.mode),
                "paused": self._paused,
                "degraded": self._degraded,
                "last_sync_ts": datetime.now(timezone.utc).isoformat(),
                "broker_type": self.cfg.broker_type,
                "market_data_source": self.cfg.market_data_source,
            }
            # Add Kraken-specific health info
            if self.circuit_breaker:
                state["circuit_breaker"] = self.circuit_breaker.status_dict()
            if self.ws_manager:
                state["ws_public_connected"] = self.ws_manager.connected
                state["ws_public_reconnects"] = self.ws_manager._reconnect_count
            if self.ws_private:
                state["ws_private_connected"] = self.ws_private.connected
                state["ws_private_reconnects"] = self.ws_private._reconnect_count
            self.repo.save_agent_state(self.mode, "default", state)
        except Exception:
            pass

    # ── Price cache ──

    async def _tick_price_cache(self) -> None:
        """Quick price cache update.

        Two paths:
          1. kraken_ws: read from MarketDataService focus buffer (no REST call)
          2. polling: fetch from RH batch API (legacy)
        """
        if self.cfg.market_data_source == "kraken_ws" and self.market_data:
            # WS-driven: read from in-memory focus buffer
            for sym, snap in self.market_data.get_all_focus_snapshots().items():
                if snap.bid > 0 and snap.ask > 0:
                    from .symbol_map import to_internal
                    internal_sym = to_internal(sym)
                    self.price_cache.record(internal_sym, snap.bid, snap.ask)
            return

        # Legacy polling path (RH)
        if self._rh_client:
            from .scanner import WATCHLIST
            try:
                batch = await self._rh_client.get_best_bid_ask_batch(WATCHLIST)
                for result in batch.get("results", []):
                    symbol = result.get("symbol", "")
                    bid = float(result.get("bid_inclusive_of_sell_spread", result.get("bid_price", 0)))
                    ask = float(result.get("ask_inclusive_of_buy_spread", result.get("ask_price", 0)))
                    if bid > 0 and ask > 0:
                        self.price_cache.record(symbol, bid, ask)
            except Exception:
                pass  # non-critical — full scan will retry

    async def _persist_candles(self) -> None:
        """Persist newly finalized candles to Supabase."""
        pending = self.candle_manager.drain_pending()
        if not pending:
            return
        try:
            rows = [
                {
                    "symbol": c.symbol,
                    "timeframe": c.timeframe,
                    "open_time": c.open_time,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "patterns": None,
                    "mode": self.mode,
                }
                for c in pending
            ]
            self.repo.upsert_candles(rows)
        except Exception as e:
            print(f"[ZOE] Candle persist error: {e}")

    async def _refresh_historical(self) -> None:
        """Refresh CoinGecko historical data every 4 hours."""
        now = time.time()
        if now < self._next_historical_refresh:
            return
        try:
            count = await self.candle_manager.load_historical()
            self._next_historical_refresh = now + 4 * 3600
            print(f"[ZOE] Historical candle refresh: {count} candles loaded")
        except Exception as e:
            print(f"[ZOE] Historical refresh failed: {e}")
            self._next_historical_refresh = now + 600  # retry in 10 min

    # ── Kraken startup / shutdown ──

    async def _start_kraken_services(self) -> None:
        """Initialize and start Kraken-specific components."""
        if self.market_data:
            print("[ZOE] Initializing MarketDataService...")
            await self.market_data.initialize()
            await self.market_data.start()
            print(f"[ZOE] MarketDataService started: focus={len(self.market_data.focus_symbols)} scout={len(self.market_data.scout_symbols)}")

        if self.ws_manager:
            print("[ZOE] Starting Kraken WS public...")
            task = asyncio.create_task(self.ws_manager.run())
            self._background_tasks.append(task)

        if self.ws_private:
            print("[ZOE] Starting Kraken WS private...")
            # Wire fill processor to WS private execution events
            if self.fill_processor:
                self.ws_private.on_execution(self.fill_processor.handle_execution)
            task = asyncio.create_task(self.ws_private.run())
            self._background_tasks.append(task)

        self._write_thought(
            f"Kraken services started: ws_public={self.ws_manager is not None}, "
            f"ws_private={self.ws_private is not None}, "
            f"market_data={self.market_data is not None}",
            thought_type="health",
        )

    async def _stop_kraken_services(self) -> None:
        """Gracefully shut down Kraken-specific components."""
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()

        if self.market_data:
            await self.market_data.stop()
        if self.ws_manager:
            await self.ws_manager.close()
        if self.ws_private:
            await self.ws_private.stop()

    # ── Main loop ──

    async def run_forever(self) -> None:
        next_order_poll = 0.0
        next_scan = 0.0
        next_tick = 0.0
        next_reposition = 0.0
        scan_interval = 300   # full scan + signal pipeline every 5 min
        tick_interval = 60    # price cache tick every 60s (fast history build)
        reposition_interval = 60  # repositioner check every 60s
        print(f"[ZOE] Crypto trader service started (mode={self.mode}, broker={self.cfg.broker_type}, data={self.cfg.market_data_source})")
        print(f"[ZOE] Pipeline: tick={tick_interval}s -> scan={scan_interval}s -> signals -> auto-execute")

        self._write_thought(
            f"Crypto trader service started (mode={self.mode}, broker={self.cfg.broker_type}, "
            f"data_source={self.cfg.market_data_source}). "
            f"Pipeline: price tick every {tick_interval}s, full scan every {scan_interval}s, signal engine active.",
            thought_type="health",
        )

        # ── Start Kraken WS services if configured ──
        if self.cfg.market_data_source == "kraken_ws":
            try:
                await self._start_kraken_services()
            except Exception as e:
                print(f"[ZOE] Kraken service startup failed: {e}")
                self._write_thought(f"Kraken startup failed: {e}", thought_type="error")
                # Fall back to polling if WS startup fails
                self.cfg.market_data_source = "polling"

        try:
            while True:
                now = time.time()
                self._cycle_count += 1
                try:
                    # Update circuit breaker state
                    if self.circuit_breaker and self.market_data:
                        self.circuit_breaker.check(self.market_data)

                    # Fast price tick — build history between scans
                    if now >= next_tick:
                        await self._tick_price_cache()
                        next_tick = now + tick_interval

                    # Exit checks run EVERY tick — critical for stop-loss/TP
                    await self._check_exits()

                    if now >= next_order_poll and not self._paused:
                        await self.poll_open_orders()
                        next_order_poll = now + self.cfg.order_poll_interval_seconds

                    health = await self.reconcile()

                    self._write_heartbeats(health)

                    cash_snap = self.repo.latest_cash_snapshot(self.mode)
                    equity = float((cash_snap or {}).get("buying_power", 0))
                    self._write_pnl_snapshot(equity)

                    # Full scan + signal pipeline
                    if now >= next_scan:
                        await self._run_scan()
                        next_scan = now + scan_interval

                    # Repositioner: cancel stale limit orders
                    if self.repositioner and now >= next_reposition:
                        try:
                            cancelled = await self.repositioner.check_and_cancel_stale()
                            if cancelled:
                                self._write_thought(
                                    f"Repositioner cancelled {len(cancelled)} stale orders: {cancelled}",
                                    thought_type="repositioner",
                                )
                        except Exception as e:
                            logger.warning("Repositioner error: %s", e)
                        next_reposition = now + reposition_interval

                    # Persist finalized candles to Supabase
                    await self._persist_candles()

                    # Refresh CoinGecko historical data periodically
                    await self._refresh_historical()

                    # Save agent state every 5 cycles
                    if self._cycle_count % 5 == 0:
                        self._save_agent_state_snapshot()

                except Exception as e:
                    import traceback
                    self.audit.write("crypto_loop_error", error=str(e))
                    print(f"[ZOE] Reconcile loop error: {e}")
                    traceback.print_exc()
                await asyncio.sleep(self.cfg.reconcile_interval_seconds)
        finally:
            # Graceful shutdown
            await self._stop_kraken_services()
