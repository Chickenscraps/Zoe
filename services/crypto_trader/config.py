from __future__ import annotations

import os
from dataclasses import dataclass


CONFIRM_PHRASE = "I UNDERSTAND THIS IS REAL MONEY"
KRAKEN_CONFIRM_PHRASE = "I UNDERSTAND THIS IS REAL MONEY ON KRAKEN"


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass
class CryptoTraderConfig:
    admin_user_id: str = os.getenv("ADMIN_USER_ID", "")
    mode: str = os.getenv("MODE_LOCK", "paper")

    # ── Broker selection ──
    broker_type: str = os.getenv("BROKER_TYPE", "paper")  # paper | robinhood | kraken

    # ── Robinhood (legacy) ──
    rh_live_trading: bool = _bool("RH_LIVE_TRADING", False)
    rh_live_confirm: str = os.getenv("RH_LIVE_CONFIRM", "")
    rh_crypto_api_key: str = os.getenv("RH_CRYPTO_API_KEY", "")
    rh_crypto_private_key_seed: str = os.getenv("RH_CRYPTO_PRIVATE_KEY_SEED", "")
    rh_crypto_base_url: str = os.getenv("RH_CRYPTO_BASE_URL", "https://trading.robinhood.com")

    # ── Kraken ──
    kraken_api_key: str = os.getenv("KRAKEN_API_KEY", "")
    kraken_api_secret: str = os.getenv("KRAKEN_API_SECRET", "")
    kraken_base_url: str = os.getenv("KRAKEN_BASE_URL", "https://api.kraken.com")
    kraken_ws_url: str = os.getenv("KRAKEN_WS_URL", "wss://ws.kraken.com/v2")
    kraken_ws_auth_url: str = os.getenv("KRAKEN_WS_AUTH_URL", "wss://ws-auth.kraken.com/v2")
    kraken_live_trading: bool = _bool("KRAKEN_LIVE_TRADING", False)
    kraken_live_confirm: str = os.getenv("KRAKEN_LIVE_CONFIRM", "")

    # ── Market data source ──
    market_data_source: str = os.getenv("MARKET_DATA_SOURCE", "polling")  # polling | kraken_ws

    # ── Trade limits ──
    max_notional_per_trade: float = float(os.getenv("MAX_NOTIONAL_PER_TRADE", "25"))
    max_daily_notional: float = float(os.getenv("MAX_DAILY_NOTIONAL", "50"))
    max_open_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
    min_notional_per_trade: float = float(os.getenv("MIN_NOTIONAL_PER_TRADE", "15"))
    stop_trading_on_degraded: bool = _bool("STOP_TRADING_ON_DEGRADED", True)
    starting_equity: float = float(os.getenv("STARTING_EQUITY", "2000"))

    # ── Timing ──
    reconcile_interval_seconds: int = int(os.getenv("RECONCILE_INTERVAL_SECONDS", "60"))
    order_poll_interval_seconds: int = int(os.getenv("ORDER_POLL_INTERVAL_SECONDS", "5"))

    # ── Rate limiting (Kraken Intermediate tier) ──
    kraken_rate_limit_calls: int = int(os.getenv("KRAKEN_RATE_LIMIT_CALLS", "20"))
    kraken_rate_limit_decay: float = float(os.getenv("KRAKEN_RATE_LIMIT_DECAY", "0.5"))

    # ── Circuit breaker ──
    stale_data_threshold_s: float = float(os.getenv("STALE_DATA_THRESHOLD_S", "5"))
    repositioner_timeout_s: float = float(os.getenv("REPOSITIONER_TIMEOUT_S", "300"))

    def __post_init__(self) -> None:
        if self.mode not in ("paper", "live"):
            raise ValueError(f"MODE_LOCK must be 'paper' or 'live', got '{self.mode}'")
        if self.broker_type not in ("paper", "robinhood", "kraken"):
            raise ValueError(f"BROKER_TYPE must be 'paper', 'robinhood', or 'kraken', got '{self.broker_type}'")

    def live_ready(self) -> bool:
        """Check if live trading is enabled and confirmed.

        Supports both Robinhood and Kraken brokers:
        - Robinhood: RH_LIVE_TRADING=true + RH_LIVE_CONFIRM matches CONFIRM_PHRASE
        - Kraken: KRAKEN_LIVE_TRADING=true + KRAKEN_LIVE_CONFIRM matches KRAKEN_CONFIRM_PHRASE
        - Paper: always False (paper mode never places real orders)
        """
        if self.broker_type == "robinhood":
            return self.rh_live_trading and self.rh_live_confirm == CONFIRM_PHRASE
        if self.broker_type == "kraken":
            return self.kraken_live_trading and self.kraken_live_confirm == KRAKEN_CONFIRM_PHRASE
        # paper broker is never "live ready"
        return False

    def validate_mode(self) -> None:
        if self.mode == "live" and not self.live_ready():
            raise RuntimeError(
                f"MODE_LOCK=live but live_ready() is False for broker_type={self.broker_type}. "
                "Set the appropriate LIVE_TRADING=1 and LIVE_CONFIRM env vars."
            )
