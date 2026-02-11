from __future__ import annotations

import os
from dataclasses import dataclass


CONFIRM_PHRASE = "I UNDERSTAND THIS IS REAL MONEY"


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass
class CryptoTraderConfig:
    admin_user_id: str = os.getenv("ADMIN_USER_ID", "")
    rh_live_trading: bool = _bool("RH_LIVE_TRADING", False)
    rh_live_confirm: str = os.getenv("RH_LIVE_CONFIRM", "")
    max_notional_per_trade: float = float(os.getenv("MAX_NOTIONAL_PER_TRADE", "10"))
    max_daily_notional: float = float(os.getenv("MAX_DAILY_NOTIONAL", "50"))
    max_open_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
    stop_trading_on_degraded: bool = _bool("STOP_TRADING_ON_DEGRADED", True)
    reconcile_interval_seconds: int = int(os.getenv("RECONCILE_INTERVAL_SECONDS", "60"))
    order_poll_interval_seconds: int = int(os.getenv("ORDER_POLL_INTERVAL_SECONDS", "5"))

    def live_ready(self) -> bool:
        return self.rh_live_trading and self.rh_live_confirm == CONFIRM_PHRASE
