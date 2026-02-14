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
    mode: str = os.getenv("MODE_LOCK", "paper")

    # Exchange selection
    exchange: str = os.getenv("CRYPTO_EXCHANGE", "kraken")

    # Kraken credentials
    kraken_api_key: str = os.getenv("KRAKEN_API_KEY", "")
    kraken_api_secret: str = os.getenv("KRAKEN_API_SECRET", "")
    kraken_use_websocket: bool = _bool("KRAKEN_USE_WEBSOCKET", True)

    # Robinhood credentials (legacy)
    rh_live_trading: bool = _bool("RH_LIVE_TRADING", False)
    rh_live_confirm: str = os.getenv("RH_LIVE_CONFIRM", "")

    # Live trading gate
    live_trading: bool = _bool("LIVE_TRADING", False)
    live_confirm: str = os.getenv("LIVE_CONFIRM", "")

    # Risk limits
    max_notional_per_trade: float = float(os.getenv("MAX_NOTIONAL_PER_TRADE", "25"))
    max_daily_notional: float = float(os.getenv("MAX_DAILY_NOTIONAL", "50"))
    max_open_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
    min_notional_per_trade: float = float(os.getenv("MIN_NOTIONAL_PER_TRADE", "15"))
    stop_trading_on_degraded: bool = _bool("STOP_TRADING_ON_DEGRADED", True)
    starting_equity: float = float(os.getenv("STARTING_EQUITY", "2000"))
    reconcile_interval_seconds: int = int(os.getenv("RECONCILE_INTERVAL_SECONDS", "60"))
    order_poll_interval_seconds: int = int(os.getenv("ORDER_POLL_INTERVAL_SECONDS", "5"))

    def __post_init__(self) -> None:
        if self.mode not in ("paper", "live"):
            raise ValueError(f"MODE_LOCK must be 'paper' or 'live', got '{self.mode}'")
        if self.exchange not in ("kraken", "robinhood"):
            raise ValueError(f"CRYPTO_EXCHANGE must be 'kraken' or 'robinhood', got '{self.exchange}'")

    def live_ready(self) -> bool:
        if self.exchange == "kraken":
            return self.live_trading and self.live_confirm == CONFIRM_PHRASE
        # Legacy Robinhood path
        return self.rh_live_trading and self.rh_live_confirm == CONFIRM_PHRASE

    def validate_mode(self) -> None:
        if self.mode == "live" and not self.live_ready():
            raise RuntimeError(
                f"MODE_LOCK=live but live_ready() is False — "
                f"set LIVE_TRADING=1 and LIVE_CONFIRM for {self.exchange}"
            )
