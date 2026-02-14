from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from .broker import Broker, KrakenBroker
from .candle_manager import CandleManager
from .config import CONFIRM_PHRASE, CryptoTraderConfig
from .logger import JsonAuditLogger
from .price_cache import PriceCache
from .repository import CryptoRepository
from .scanner import scan_candidates
from .signals import generate_signals, Signal
from .exit_manager import SmartExitManager, ExitConfig, ExitReason, ExitUrgency
from .consensus import ConsensusEngine


@dataclass
class HealthState:
    status: str
    reason: str
    last_reconcile_at: str | None
    daily_notional_used: float
    live_enabled: bool
    open_orders: int


class CryptoTraderService:
    def __init__(self, broker: Broker, repository: CryptoRepository, config: CryptoTraderConfig | None = None):
        self.broker = broker
        self.repo = repository
        self.cfg = config or CryptoTraderConfig()
        self.mode = self.cfg.mode
        self.audit = JsonAuditLogger()
        self.price_cache = PriceCache(capacity_per_symbol=288)  # 24h at 5-min ticks
        self.candle_manager = CandleManager()
        self.price_cache.set_candle_manager(self.candle_manager)
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

    def _require_admin(self, initiator_id: str) -> None:
        if initiator_id != self.cfg.admin_user_id:
            raise PermissionError("Crypto controls are admin-only.")

    def set_live(self, initiator_id: str, enabled: bool, confirmation: str = "") -> str:
        self._require_admin(initiator_id)
        if enabled and confirmation != CONFIRM_PHRASE:
            raise ValueError("Live mode denied: missing exact confirmation phrase")
        self.cfg.live_trading = enabled
        self.cfg.live_confirm = confirmation if enabled else ""
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
        if not normalized.endswith("-USD"):
            raise ValueError("Only crypto USD pairs are allowed")
        return normalized

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

        safe_symbol = self._validate_symbol(symbol)
        order_notional = notional or ((qty or 0) * (limit_price or 0))
        self._enforce_trade_limits(notional=order_notional, symbol=safe_symbol)

        order = await self.broker.place_order(
            symbol=safe_symbol,
            side=side,
            qty=qty or 0,
            limit_price=limit_price or 0,
        )
        order_id = order.get("id", str(uuid.uuid4()))
        self.repo.insert_order(
            {
                "id": order_id,
                "client_order_id": order.get("client_order_id", f"zoe-{safe_symbol.lower()}-{uuid.uuid4()}"),
                "symbol": safe_symbol,
                "side": side,
                "order_type": order_type,
                "qty": qty,
                "notional": notional,
                "status": order.get("status", "submitted"),
                "raw_response": order.get("raw", {}),
                "mode": self.mode,
            }
        )
        self.repo.set_daily_notional(date.today(), self.repo.get_daily_notional(date.today(), self.mode) + order_notional, self.mode)
        self.audit.write("crypto_order_submitted", symbol=safe_symbol, side=side, notional=order_notional, mode=self.mode)
        return order

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

    async def reconcile(self) -> HealthState:
        if self.mode == "paper":
            return await self._reconcile_paper()
        return await self._reconcile_live()

    async def _reconcile_paper(self) -> HealthState:
        """Paper mode: use local ledger only, no exchange API calls."""
        local_cash, local_holdings = self._compute_local_ledger()
        if local_cash == 0.0 and not local_holdings:
            local_cash = float(getattr(self.cfg, "starting_equity", 2000.0))

        total_value = 0.0
        self.repo.insert_cash_snapshot(cash_available=local_cash, buying_power=local_cash, mode=self.mode)
        self.repo.insert_holdings_snapshot(holdings=local_holdings, total_value=total_value, mode=self.mode)
        self.repo.insert_reconciliation_event(
            {
                "taken_at": datetime.now(timezone.utc).isoformat(),
                "local_cash": local_cash,
                "rh_cash": local_cash,
                "cash_diff": 0.0,
                "local_holdings": local_holdings,
                "rh_holdings": local_holdings,
                "status": "ok",
                "reason": "paper mode - local ledger only",
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
        """Live mode: reconcile against exchange API via broker abstraction."""
        exchange_cash = await self.broker.get_cash()
        exchange_positions = await self.broker.get_positions()
        total_usd = await self.broker.get_total_usd()
        crypto_value = total_usd - exchange_cash

        local_cash, local_holdings = self._compute_local_ledger()
        cash_diff = local_cash - exchange_cash
        holding_diff = {
            sym: local_holdings.get(sym, 0.0) - exchange_positions.get(sym, 0.0)
            for sym in sorted(set(local_holdings) | set(exchange_positions))
            if abs(local_holdings.get(sym, 0.0) - exchange_positions.get(sym, 0.0)) > 0.0000001
        }

        status = "ok"
        reason = ""
        if abs(cash_diff) > 1 or holding_diff:
            status = "degraded"
            reason = "Mismatch between local ledger and exchange snapshots"

        self.repo.insert_cash_snapshot(cash_available=exchange_cash, buying_power=exchange_cash, mode=self.mode)
        self.repo.insert_holdings_snapshot(holdings=exchange_positions, total_value=crypto_value, mode=self.mode)
        self.repo.insert_reconciliation_event(
            {
                "taken_at": datetime.now(timezone.utc).isoformat(),
                "local_cash": local_cash,
                "rh_cash": exchange_cash,
                "cash_diff": cash_diff,
                "local_holdings": local_holdings,
                "rh_holdings": exchange_positions,
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

    async def poll_open_orders(self) -> None:
        """Poll open orders from exchange and update DB."""
        if isinstance(self.broker, KrakenBroker):
            exchange_orders = await self.broker.get_open_orders()
            db_orders = self.repo.list_open_orders(self.mode)
            exchange_order_ids = {eo["order_id"] for eo in exchange_orders}

            # Check DB orders that are no longer in exchange open orders → filled/canceled
            for db_order in db_orders:
                if db_order["id"] not in exchange_order_ids:
                    try:
                        result = await self.broker.client.query_orders([db_order["id"]])
                        for txid, order_data in result.items():
                            final_status = order_data.get("status", "closed")
                            status_map = {"open": "submitted", "closed": "filled", "canceled": "canceled", "expired": "canceled"}
                            mapped = status_map.get(final_status, final_status)
                            self.repo.update_order_status(db_order["id"], mapped, order_data)

                            vol_exec = float(order_data.get("vol_exec", 0))
                            if vol_exec > 0:
                                cost = float(order_data.get("cost", 0))
                                fee = float(order_data.get("fee", 0))
                                avg_price = cost / vol_exec if vol_exec > 0 else 0
                                descr = order_data.get("descr", {})
                                self.repo.upsert_fill({
                                    "order_id": txid,
                                    "fill_id": f"kraken-{txid}",
                                    "symbol": db_order.get("symbol", ""),
                                    "side": descr.get("type", db_order.get("side", "")),
                                    "qty": vol_exec,
                                    "price": avg_price,
                                    "fee": fee,
                                    "executed_at": datetime.fromtimestamp(
                                        float(order_data.get("closetm", time.time())), tz=timezone.utc
                                    ).isoformat(),
                                    "mode": self.mode,
                                })
                    except Exception as e:
                        print(f"[ZOE] Order query failed for {db_order['id']}: {e}")
                    await self.reconcile()
        else:
            for order in self.repo.list_open_orders(self.mode):
                rh_order = await self.broker.client.get_order(order["id"])
                status = rh_order.get("status", order.get("status", "submitted"))
                self.repo.update_order_status(order["id"], status, rh_order)

                fills = await self.broker.client.get_order_fills(order["id"])
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

    def get_health(self, reason_override: str = "") -> HealthState:
        daily_notional = self.repo.get_daily_notional(date.today(), self.mode)
        return HealthState(
            status="DEGRADED" if self._degraded else "LIVE",
            reason=reason_override,
            last_reconcile_at=self._last_reconcile_at,
            daily_notional_used=daily_notional,
            live_enabled=self.cfg.live_ready(),
            open_orders=len(self.repo.list_open_orders(self.mode)),
        )

    async def run_once(self) -> None:
        await self.poll_open_orders()
        await self.reconcile()

    def _write_heartbeats(self, health: HealthState) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        exchange_name = self.cfg.exchange + "_api"
        components = [
            (exchange_name, "ok" if not self._degraded else "warning"),
            ("reconciliation_engine", "ok" if health.status == "LIVE" else "warning"),
            ("snapshot_store", "ok"),
            ("discord_control", "ok"),
        ]
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

    def _get_open_positions(self) -> set[str]:
        holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
        return {sym for sym, qty in holdings.items() if float(qty) > 0}

    async def _run_scan(self) -> None:
        """Full pipeline: scan -> score -> signal -> (optional) auto-execute."""
        try:
            candidates = await scan_candidates(self.broker, self.price_cache, self.candle_manager)
            if not candidates:
                return

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

            open_positions = self._get_open_positions()
            signals = generate_signals(
                candidates=candidates,
                price_cache=self.price_cache,
                open_positions=open_positions,
                max_notional=self.cfg.max_notional_per_trade,
                max_signals=self.cfg.max_open_positions,
            )

            actionable = [s for s in signals if s.is_actionable]

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

            for signal in actionable:
                await self._execute_signal(signal)

        except Exception as e:
            import traceback
            print(f"[ZOE] Scan pipeline error: {e}")
            traceback.print_exc()

    async def _execute_signal(self, signal: Signal) -> None:
        sym = signal.symbol
        action = signal.action
        notional = signal.suggested_notional

        if self._paused:
            self._write_thought(f"Signal {action} {sym} skipped -- trading paused", thought_type="signal", symbol=sym)
            return
        if time.time() < self._safe_mode_until:
            self._write_thought(f"Signal {action} {sym} skipped -- safe mode cooldown", thought_type="signal", symbol=sym)
            return
        if self._degraded and self.cfg.stop_trading_on_degraded:
            self._write_thought(f"Signal {action} {sym} skipped -- degraded state", thought_type="signal", symbol=sym)
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

        self._write_thought(
            f"Executing {action} {sym}: ${notional:.2f} notional | confidence={signal.confidence:.0%} | {signal.reason}",
            thought_type="signal",
            symbol=sym,
            metadata=signal.to_dict(),
        )
        self.audit.write(
            "crypto_signal_execute",
            symbol=sym, action=action, confidence=signal.confidence,
            notional=notional, reason=signal.reason, strategy=signal.strategy, mode=self.mode,
        )
        print(f"[ZOE] SIGNAL: {action} {sym} ${notional:.2f} (conf={signal.confidence:.0%}) -- {signal.reason}")

        if not self.cfg.live_ready():
            self._write_thought(
                f"PAPER {action} {sym}: ${notional:.2f} (would execute if live)",
                thought_type="paper_trade", symbol=sym, metadata=signal.to_dict(),
            )
            print(f"[ZOE] PAPER TRADE: {action} {sym} ${notional:.2f}")
            if action == "BUY":
                snap = self.price_cache.snapshot(sym)
                entry_price = snap.get("mid", 0)
                if entry_price > 0:
                    self.exit_manager.register_position(symbol=sym, entry_price=entry_price, entry_time=datetime.now(timezone.utc))
            return

        try:
            order = await self.place_order(
                initiator_id=self.cfg.admin_user_id, symbol=sym, side=side, notional=notional, order_type="market",
            )
            self._write_thought(
                f"Order placed: {action} {sym} ${notional:.2f} -> {order.get('status', 'submitted')}",
                thought_type="order", symbol=sym,
                metadata={"order_id": order.get("id"), "signal": signal.to_dict()},
            )
            if action == "BUY":
                snap = self.price_cache.snapshot(sym)
                entry_price = snap.get("mid", 0)
                if entry_price > 0:
                    self.exit_manager.register_position(symbol=sym, entry_price=entry_price, entry_time=datetime.now(timezone.utc))
        except Exception as e:
            self._write_thought(
                f"Order FAILED: {action} {sym} ${notional:.2f} -- {e}",
                thought_type="order_error", symbol=sym,
                metadata={"error": str(e), "signal": signal.to_dict()},
            )
            print(f"[ZOE] ORDER FAILED for {sym}: {e}")

    async def _check_exits(self) -> None:
        try:
            holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
            open_symbols = {sym for sym, qty in holdings.items() if float(qty) > 0}

            for sym in open_symbols:
                if self.exit_manager.get_position_state(sym) is None:
                    snap = self.price_cache.snapshot(sym)
                    mid = snap.get("mid", 0)
                    self.exit_manager.register_position(symbol=sym, entry_price=mid, entry_time=datetime.now(timezone.utc))

            for sym in list(self.exit_manager.active_positions()):
                if sym not in open_symbols:
                    self.exit_manager.unregister_position(sym)

            for sym in open_symbols:
                snap = self.price_cache.snapshot(sym)
                current_price = snap.get("mid", 0)
                current_spread = snap.get("spread_pct", 0)
                if current_price <= 0:
                    continue
                exit_signal = self.exit_manager.check_exits(symbol=sym, current_price=current_price, current_spread_pct=current_spread)
                if exit_signal is not None:
                    await self._execute_exit(sym, exit_signal)
        except Exception as e:
            import traceback
            print(f"[ZOE] Exit check error: {e}")
            traceback.print_exc()

    async def _execute_exit(self, symbol: str, exit_signal: Any) -> None:
        self._write_thought(
            f"EXIT {symbol}: {exit_signal.reason.value} | {exit_signal.details} | P&L: {exit_signal.pnl_pct:.2%}",
            thought_type="exit_signal", symbol=symbol, metadata=exit_signal.to_dict(),
        )
        self.audit.write(
            "crypto_exit_signal", symbol=symbol, reason=exit_signal.reason.value,
            urgency=exit_signal.urgency.value, pnl_pct=exit_signal.pnl_pct, details=exit_signal.details, mode=self.mode,
        )
        print(f"[ZOE] EXIT: {exit_signal.reason.value} {symbol} ({exit_signal.pnl_pct:.2%}) -- {exit_signal.details}")

        if not self.cfg.live_ready():
            self._write_thought(
                f"PAPER EXIT {symbol}: {exit_signal.reason.value} (would sell if live)",
                thought_type="paper_exit", symbol=symbol, metadata=exit_signal.to_dict(),
            )
            print(f"[ZOE] PAPER EXIT: {symbol} {exit_signal.reason.value}")
            self.exit_manager.unregister_position(symbol)
            return

        try:
            holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
            qty = float(holdings.get(symbol, 0))
            if qty <= 0:
                self.exit_manager.unregister_position(symbol)
                return

            order = await self.place_order(
                initiator_id=self.cfg.admin_user_id, symbol=symbol, side="sell", qty=qty, order_type="market",
            )
            self._write_thought(
                f"Exit order placed: SELL {symbol} qty={qty} -> {order.get('status', 'submitted')} | reason={exit_signal.reason.value}",
                thought_type="exit_order", symbol=symbol,
                metadata={"order_id": order.get("id"), "exit": exit_signal.to_dict()},
            )
            self.exit_manager.unregister_position(symbol)
        except Exception as e:
            self._write_thought(
                f"Exit order FAILED: SELL {symbol} -- {e}",
                thought_type="exit_error", symbol=symbol,
                metadata={"error": str(e), "exit": exit_signal.to_dict()},
            )
            print(f"[ZOE] EXIT ORDER FAILED for {symbol}: {e}")

    def _save_agent_state_snapshot(self) -> None:
        try:
            holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
            cash_snap = self.repo.latest_cash_snapshot(self.mode) or {}
            self.repo.save_agent_state(self.mode, "default", {
                "open_orders": [o["id"] for o in self.repo.list_open_orders(self.mode)],
                "holdings": holdings,
                "cash_available": cash_snap.get("cash_available", 0),
                "buying_power": cash_snap.get("buying_power", 0),
                "daily_notional_used": self.repo.get_daily_notional(date.today(), self.mode),
                "paused": self._paused,
                "degraded": self._degraded,
                "last_sync_ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass

    async def _tick_price_cache(self) -> None:
        from .scanner import WATCHLIST
        try:
            if isinstance(self.broker, KrakenBroker):
                prices = await self.broker.get_ticker_prices(WATCHLIST)
                for symbol, mid in prices.items():
                    if mid > 0:
                        self.price_cache.record(symbol, mid * 0.999, mid * 1.001)
            else:
                batch = await self.broker.client.get_best_bid_ask_batch(WATCHLIST)
                for result in batch.get("results", []):
                    symbol = result.get("symbol", "")
                    bid = float(result.get("bid_inclusive_of_sell_spread", result.get("bid_price", 0)))
                    ask = float(result.get("ask_inclusive_of_buy_spread", result.get("ask_price", 0)))
                    if bid > 0 and ask > 0:
                        self.price_cache.record(symbol, bid, ask)
        except Exception:
            pass

    async def _persist_candles(self) -> None:
        pending = self.candle_manager.drain_pending()
        if not pending:
            return
        try:
            rows = [
                {
                    "symbol": c.symbol, "timeframe": c.timeframe, "open_time": c.open_time,
                    "open": c.open, "high": c.high, "low": c.low, "close": c.close,
                    "volume": c.volume, "patterns": None, "mode": self.mode,
                }
                for c in pending
            ]
            self.repo.upsert_candles(rows)
        except Exception as e:
            print(f"[ZOE] Candle persist error: {e}")

    async def _refresh_historical(self) -> None:
        now = time.time()
        if now < self._next_historical_refresh:
            return
        try:
            count = await self.candle_manager.load_historical()
            self._next_historical_refresh = now + 4 * 3600
            print(f"[ZOE] Historical candle refresh: {count} candles loaded")
        except Exception as e:
            print(f"[ZOE] Historical refresh failed: {e}")
            self._next_historical_refresh = now + 600

    async def run_forever(self) -> None:
        next_order_poll = 0.0
        next_scan = 0.0
        next_tick = 0.0
        scan_interval = 300
        tick_interval = 60
        print(f"[ZOE] Crypto trader service started (mode={self.mode}, exchange={self.cfg.exchange})")
        print(f"[ZOE] Pipeline: tick={tick_interval}s -> scan={scan_interval}s -> signals -> auto-execute")

        self._write_thought(
            f"Crypto trader service started (mode={self.mode}, exchange={self.cfg.exchange}). "
            f"Pipeline: price tick every {tick_interval}s, full scan every {scan_interval}s, signal engine active.",
            thought_type="health",
        )

        while True:
            now = time.time()
            self._cycle_count += 1
            try:
                if now >= next_tick:
                    await self._tick_price_cache()
                    next_tick = now + tick_interval

                await self._check_exits()

                if now >= next_order_poll and not self._paused:
                    await self.poll_open_orders()
                    next_order_poll = now + self.cfg.order_poll_interval_seconds

                health = await self.reconcile()
                self._write_heartbeats(health)

                cash_snap = self.repo.latest_cash_snapshot(self.mode)
                equity = float((cash_snap or {}).get("buying_power", 0))
                self._write_pnl_snapshot(equity)

                if now >= next_scan:
                    await self._run_scan()
                    next_scan = now + scan_interval

                await self._persist_candles()
                await self._refresh_historical()

                if self._cycle_count % 5 == 0:
                    self._save_agent_state_snapshot()

            except Exception as e:
                import traceback
                self.audit.write("crypto_loop_error", error=str(e))
                print(f"[ZOE] Reconcile loop error: {e}")
                traceback.print_exc()
            await asyncio.sleep(self.cfg.reconcile_interval_seconds)
