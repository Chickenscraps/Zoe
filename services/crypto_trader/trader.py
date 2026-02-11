from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from integrations.robinhood_crypto_client import RobinhoodCryptoClient
from integrations.robinhood_crypto_client.client import _sanitize

from .config import CONFIRM_PHRASE, CryptoTraderConfig
from .logger import JsonAuditLogger
from .repository import CryptoRepository


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
        self.audit = JsonAuditLogger()
        self._paused = False
        self._degraded = False
        self._last_reconcile_at: str | None = None

    def _require_admin(self, initiator_id: str) -> None:
        if initiator_id != self.cfg.admin_user_id:
            raise PermissionError("🦝 Nice try. Crypto controls are admin-only.")

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
        # Robinhood crypto trading is crypto-only; enforce USD pair format to avoid equities/options routes.
        if not normalized.endswith("-USD"):
            raise ValueError("Only Robinhood crypto USD pairs are allowed")
        return normalized

    def _enforce_trade_limits(self, *, notional: float, symbol: str) -> None:
        if notional > self.cfg.max_notional_per_trade:
            raise ValueError("Trade blocked by MAX_NOTIONAL_PER_TRADE")
        today = date.today()
        used = self.repo.get_daily_notional(today)
        if used + notional > self.cfg.max_daily_notional:
            raise ValueError("Trade blocked by MAX_DAILY_NOTIONAL")
        holdings = (self.repo.latest_holdings_snapshot() or {}).get("holdings", {})
        open_positions = [asset for asset, qty in holdings.items() if float(qty) > 0]
        if symbol not in open_positions and len(open_positions) >= self.cfg.max_open_positions:
            raise ValueError("Trade blocked by MAX_OPEN_POSITIONS")

    def place_order(self, *, initiator_id: str, symbol: str, side: str, notional: float | None = None, qty: float | None = None, order_type: str = "market", limit_price: float | None = None) -> dict[str, Any]:
        self._require_admin(initiator_id)
        if self._paused:
            raise RuntimeError("Trading paused")
        if self._degraded and self.cfg.stop_trading_on_degraded:
            raise RuntimeError("Trading frozen while DEGRADED")
        if not self.cfg.live_ready():
            raise RuntimeError("Live trading disabled (feature flag / confirmation not satisfied)")

        safe_symbol = self._validate_symbol(symbol)
        order_notional = notional or ((qty or 0) * (limit_price or 0))
        self._enforce_trade_limits(notional=order_notional, symbol=safe_symbol)

        client_order_id = f"zoe-{safe_symbol.lower()}-{uuid.uuid4()}"
        order = self.client.place_order(
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
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "raw_response": _sanitize(order),
            }
        )
        self.repo.set_daily_notional(date.today(), self.repo.get_daily_notional(date.today()) + order_notional)
        self.audit.write("crypto_order_submitted", symbol=safe_symbol, side=side, notional=order_notional, client_order_id=client_order_id)
        return order

    def _compute_local_ledger(self) -> tuple[float, dict[str, float]]:
        start_cash = float((self.repo.latest_cash_snapshot() or {}).get("cash_available", 0.0))
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

    def reconcile(self) -> HealthState:
        balances = self.client.get_account_balances()
        holdings_resp = self.client.get_holdings()

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

        self.repo.insert_cash_snapshot(cash_available=rh_cash, buying_power=rh_buying_power)
        self.repo.insert_holdings_snapshot(holdings=rh_holdings, total_value=total_value)
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
            }
        )

        self._degraded = status == "degraded"
        self._last_reconcile_at = datetime.now(timezone.utc).isoformat()
        self.audit.write("crypto_reconcile", status=status, reason=reason, cash_diff=cash_diff, holdings_diff=holding_diff)

        if self._degraded and self.cfg.stop_trading_on_degraded:
            self.audit.write("crypto_trading_frozen", reason="stop_trading_on_degraded")

        return self.get_health(reason_override=reason)

    def poll_open_orders(self) -> None:
        for order in self.repo.list_open_orders():
            rh_order = self.client.get_order(order["id"])
            status = rh_order.get("status", order.get("status", "submitted"))
            self.repo.update_order_status(order["id"], status, _sanitize(rh_order))

            fills = self.client.get_order_fills(order["id"])
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
                    }
                )
            if status in {"partially_filled", "filled", "canceled", "rejected"}:
                self.reconcile()

    def get_health(self, reason_override: str = "") -> HealthState:
        daily_notional = self.repo.get_daily_notional(date.today())
        return HealthState(
            status="DEGRADED" if self._degraded else "LIVE",
            reason=reason_override,
            last_reconcile_at=self._last_reconcile_at,
            daily_notional_used=daily_notional,
            live_enabled=self.cfg.live_ready(),
            open_orders=len(self.repo.list_open_orders()),
        )

    def run_once(self) -> None:
        self.poll_open_orders()
        self.reconcile()

    def run_forever(self) -> None:
        next_order_poll = 0.0
        while True:
            now = time.time()
            if now >= next_order_poll and not self._paused:
                self.poll_open_orders()
                next_order_poll = now + self.cfg.order_poll_interval_seconds
            self.reconcile()
            time.sleep(self.cfg.reconcile_interval_seconds)
