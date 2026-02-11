from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from integrations.robinhood_crypto_client import RobinhoodCryptoClient
from integrations.robinhood_crypto_client.client import _sanitize

from .config import CONFIRM_PHRASE, CryptoTraderConfig
from .logger import JsonAuditLogger
from .price_cache import PriceCache
from .repository import CryptoRepository
from .scanner import scan_candidates
from .signals import generate_signals, Signal


@dataclass
class HealthState:
    status: str
    reason: str
    last_reconcile_at: str | None
    daily_notional_used: float
    live_enabled: bool
    open_orders: int


class CryptoTraderService:
    def __init__(self, client: RobinhoodCryptoClient, repository: CryptoRepository, config: CryptoTraderConfig | None = None):
        self.client = client
        self.repo = repository
        self.cfg = config or CryptoTraderConfig()
        self.mode = self.cfg.mode
        self.audit = JsonAuditLogger()
        self.price_cache = PriceCache(capacity_per_symbol=288)  # 24h at 5-min ticks
        self._paused = False
        self._degraded = False
        self._last_reconcile_at: str | None = None
        self._safe_mode_until: float = 0.0
        self._cycle_count: int = 0

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
        if not normalized.endswith("-USD"):
            raise ValueError("Only Robinhood crypto USD pairs are allowed")
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

        client_order_id = f"zoe-{safe_symbol.lower()}-{uuid.uuid4()}"
        order = await self.client.place_order(
            symbol=safe_symbol,
            side=side,
            order_type=order_type,
            client_order_id=client_order_id,
            notional=notional,
            qty=qty,
            limit_price=limit_price,
        )
        self.repo.insert_order(
            {
                "id": order.get("id", client_order_id),
                "client_order_id": client_order_id,
                "symbol": safe_symbol,
                "side": side,
                "order_type": order_type,
                "qty": qty,
                "notional": notional,
                "status": order.get("status", "submitted"),
                "raw_response": _sanitize(order),
                "mode": self.mode,
            }
        )
        self.repo.set_daily_notional(date.today(), self.repo.get_daily_notional(date.today(), self.mode) + order_notional, self.mode)
        self.audit.write("crypto_order_submitted", symbol=safe_symbol, side=side, notional=order_notional, client_order_id=client_order_id, mode=self.mode)
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
        balances = await self.client.get_account_balances()
        holdings_resp = await self.client.get_holdings()

        rh_cash = float(balances.get("cash_available") or balances.get("cash") or 0.0)
        rh_buying_power = float(balances.get("buying_power") or rh_cash)
        rh_holdings = {item["symbol"]: float(item.get("quantity", 0.0)) for item in holdings_resp.get("results", holdings_resp if isinstance(holdings_resp, list) else [])}
        total_value = sum(float(item.get("market_value", 0.0)) for item in holdings_resp.get("results", [])) if isinstance(holdings_resp, dict) else 0.0

        local_cash, local_holdings = self._compute_local_ledger()
        cash_diff = local_cash - rh_cash
        holding_diff = {
            sym: local_holdings.get(sym, 0.0) - rh_holdings.get(sym, 0.0)
            for sym in sorted(set(local_holdings) | set(rh_holdings))
            if abs(local_holdings.get(sym, 0.0) - rh_holdings.get(sym, 0.0)) > 0.0000001
        }

        status = "ok"
        reason = ""
        if abs(cash_diff) > 1 or holding_diff:
            status = "degraded"
            reason = "Mismatch between local ledger and Robinhood snapshots"

        self.repo.insert_cash_snapshot(cash_available=rh_cash, buying_power=rh_buying_power, mode=self.mode)
        self.repo.insert_holdings_snapshot(holdings=rh_holdings, total_value=total_value, mode=self.mode)
        self.repo.insert_reconciliation_event(
            {
                "taken_at": datetime.now(timezone.utc).isoformat(),
                "local_cash": local_cash,
                "rh_cash": rh_cash,
                "cash_diff": cash_diff,
                "local_holdings": local_holdings,
                "rh_holdings": rh_holdings,
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
        for order in self.repo.list_open_orders(self.mode):
            rh_order = await self.client.get_order(order["id"])
            status = rh_order.get("status", order.get("status", "submitted"))
            self.repo.update_order_status(order["id"], status, _sanitize(rh_order))

            fills = await self.client.get_order_fills(order["id"])
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
        components = [
            ("robinhood_api", "ok" if not self._degraded else "warning"),
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
        """Get set of symbols with open positions."""
        holdings = (self.repo.latest_holdings_snapshot(self.mode) or {}).get("holdings", {})
        return {sym for sym, qty in holdings.items() if float(qty) > 0}

    async def _run_scan(self) -> None:
        """Full pipeline: scan -> score -> signal -> (optional) auto-execute."""
        try:
            # Phase 1: Scan — fetch prices, update cache, score
            candidates = await scan_candidates(self.client, self.price_cache)
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
        """Execute a single signal — place order if all checks pass.

        In paper mode: simulates by logging + recording the order intent.
        Guards: paused, safe_mode, degraded, notional limits.
        """
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
        if notional <= 0:
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
            return

        # Live execution
        try:
            order = await self.place_order(
                initiator_id=self.cfg.admin_user_id,
                symbol=sym,
                side=side,
                notional=notional,
                order_type="market",
            )
            self._write_thought(
                f"Order placed: {action} {sym} ${notional:.2f} -> {order.get('status', 'submitted')}",
                thought_type="order",
                symbol=sym,
                metadata={"order_id": order.get("id"), "signal": signal.to_dict()},
            )
        except Exception as e:
            self._write_thought(
                f"Order FAILED: {action} {sym} ${notional:.2f} -- {e}",
                thought_type="order_error",
                symbol=sym,
                metadata={"error": str(e), "signal": signal.to_dict()},
            )
            print(f"[ZOE] ORDER FAILED for {sym}: {e}")

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
        """Quick price cache update — fetch batch bid/ask and record ticks.

        Runs more frequently than the full scan to build up price history
        faster. Does NOT score or generate signals (that's _run_scan's job).
        """
        from .scanner import WATCHLIST
        try:
            batch = await self.client.get_best_bid_ask_batch(WATCHLIST)
            for result in batch.get("results", []):
                symbol = result.get("symbol", "")
                bid = float(result.get("bid_inclusive_of_sell_spread", result.get("bid_price", 0)))
                ask = float(result.get("ask_inclusive_of_buy_spread", result.get("ask_price", 0)))
                if bid > 0 and ask > 0:
                    self.price_cache.record(symbol, bid, ask)
        except Exception:
            pass  # non-critical — full scan will retry

    async def run_forever(self) -> None:
        next_order_poll = 0.0
        next_scan = 0.0
        next_tick = 0.0
        scan_interval = 300   # full scan + signal pipeline every 5 min
        tick_interval = 60    # price cache tick every 60s (fast history build)
        print(f"[ZOE] Crypto trader service started (mode={self.mode})")
        print(f"[ZOE] Pipeline: tick={tick_interval}s -> scan={scan_interval}s -> signals -> auto-execute")

        self._write_thought(
            f"Crypto trader service started (mode={self.mode}). "
            f"Pipeline: price tick every {tick_interval}s, full scan every {scan_interval}s, signal engine active.",
            thought_type="health",
        )

        while True:
            now = time.time()
            self._cycle_count += 1
            try:
                # Fast price tick — build history between scans
                if now >= next_tick:
                    await self._tick_price_cache()
                    next_tick = now + tick_interval

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

                # Save agent state every 5 cycles
                if self._cycle_count % 5 == 0:
                    self._save_agent_state_snapshot()

            except Exception as e:
                import traceback
                self.audit.write("crypto_loop_error", error=str(e))
                print(f"[ZOE] Reconcile loop error: {e}")
                traceback.print_exc()
            await asyncio.sleep(self.cfg.reconcile_interval_seconds)
