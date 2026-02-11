from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [s.strip() for s in raw.split(",") if s.strip()]


CONFIRM_PHRASE = "I UNDERSTAND THIS IS REAL MONEY"


@dataclass
class EdgeFactoryConfig:
    # ── Mode ──────────────────────────────────────────────────
    mode: str = field(default_factory=lambda: os.getenv("EDGE_FACTORY_MODE", "disabled"))
    admin_user_id: str = field(default_factory=lambda: os.getenv("ADMIN_USER_ID", ""))

    # ── Symbol Universe ───────────────────────────────────────
    symbols: list[str] = field(
        default_factory=lambda: _list("EDGE_FACTORY_SYMBOLS", "BTC-USD,ETH-USD,DOGE-USD,SOL-USD")
    )

    # ── Polling Intervals (seconds) ──────────────────────────
    trends_poll_interval: int = field(default_factory=lambda: _int("EDGE_FACTORY_TRENDS_POLL", 3600))
    funding_poll_interval: int = field(default_factory=lambda: _int("EDGE_FACTORY_FUNDING_POLL", 300))
    market_poll_interval: int = field(default_factory=lambda: _int("EDGE_FACTORY_MARKET_POLL", 60))

    # ── Signal Thresholds (V1 Regime-Adaptive Sniper) ────────
    trend_z_threshold: float = field(default_factory=lambda: _float("EDGE_FACTORY_TREND_Z_THRESHOLD", 0.8))
    funding_rate_max: float = field(default_factory=lambda: _float("EDGE_FACTORY_FUNDING_RATE_MAX", 0.0005))
    corwin_schultz_max: float = field(default_factory=lambda: _float("EDGE_FACTORY_CORWIN_SCHULTZ_MAX", 0.006))

    # ── Position Sizing ──────────────────────────────────────
    account_equity: float = field(default_factory=lambda: _float("EDGE_FACTORY_ACCOUNT_EQUITY", 150.0))
    max_position_pct: float = field(default_factory=lambda: _float("EDGE_FACTORY_MAX_POSITION_PCT", 0.15))
    kelly_fraction: float = field(default_factory=lambda: _float("EDGE_FACTORY_KELLY_FRACTION", 0.5))
    max_notional_per_trade: float = field(default_factory=lambda: _float("MAX_NOTIONAL_PER_TRADE", 25.0))
    max_daily_notional: float = field(default_factory=lambda: _float("MAX_DAILY_NOTIONAL", 150.0))
    max_open_positions: int = field(default_factory=lambda: _int("MAX_OPEN_POSITIONS", 5))

    # ── Risk Management ──────────────────────────────────────
    take_profit_pct: float = field(default_factory=lambda: _float("EDGE_FACTORY_TP_PCT", 0.04))
    stop_loss_pct: float = field(default_factory=lambda: _float("EDGE_FACTORY_SL_PCT", 0.02))
    max_drawdown_24h_pct: float = field(default_factory=lambda: _float("EDGE_FACTORY_MAX_DD_24H", 0.20))
    portfolio_heat_max: float = field(default_factory=lambda: _float("EDGE_FACTORY_HEAT_MAX", 0.60))
    consecutive_loss_max: int = field(default_factory=lambda: _int("EDGE_FACTORY_CONSEC_LOSS_MAX", 4))
    limit_order_timeout_sec: int = field(default_factory=lambda: _int("EDGE_FACTORY_LIMIT_TIMEOUT", 60))
    circuit_breaker_sleep_sec: int = field(default_factory=lambda: _int("EDGE_FACTORY_CIRCUIT_BREAKER", 900))
    position_timeout_hours: int = field(default_factory=lambda: _int("EDGE_FACTORY_POS_TIMEOUT_HOURS", 48))

    # ── Data Staleness Thresholds (seconds) ──────────────────
    trends_stale_after: int = field(default_factory=lambda: _int("EDGE_FACTORY_TRENDS_STALE", 14400))
    funding_stale_after: int = field(default_factory=lambda: _int("EDGE_FACTORY_FUNDING_STALE", 600))
    market_stale_after: int = field(default_factory=lambda: _int("EDGE_FACTORY_MARKET_STALE", 120))

    # ── Execution Quality (V2) ─────────────────────────────
    quote_stale_sec: int = field(default_factory=lambda: _int("EDGE_FACTORY_QUOTE_STALE", 10))
    passive_ttl_sec: int = field(default_factory=lambda: _int("EDGE_FACTORY_PASSIVE_TTL", 90))
    normal_ttl_sec: int = field(default_factory=lambda: _int("EDGE_FACTORY_NORMAL_TTL", 60))
    panic_ttl_sec: int = field(default_factory=lambda: _int("EDGE_FACTORY_PANIC_TTL", 15))
    max_order_retries: int = field(default_factory=lambda: _int("EDGE_FACTORY_MAX_ORDER_RETRIES", 2))
    max_avg_slippage_bps: float = field(default_factory=lambda: _float("EDGE_FACTORY_MAX_AVG_SLIPPAGE", 50.0))
    max_spread_pct_entry: float = field(default_factory=lambda: _float("EDGE_FACTORY_MAX_SPREAD_ENTRY", 0.008))
    min_buf_pct: float = field(default_factory=lambda: _float("EDGE_FACTORY_MIN_BUF_PCT", 0.0005))
    max_buf_pct: float = field(default_factory=lambda: _float("EDGE_FACTORY_MAX_BUF_PCT", 0.002))

    # ── Churn Control (V2) ─────────────────────────────────
    symbol_cooldown_hours: int = field(default_factory=lambda: _int("EDGE_FACTORY_SYMBOL_COOLDOWN", 4))
    min_expected_move_pct: float = field(default_factory=lambda: _float("EDGE_FACTORY_MIN_EXPECTED_MOVE", 0.03))
    daily_turnover_cap_mult: float = field(default_factory=lambda: _float("EDGE_FACTORY_DAILY_TURNOVER_CAP", 2.0))
    min_trade_notional: float = field(default_factory=lambda: _float("EDGE_FACTORY_MIN_TRADE_NOTIONAL", 1.0))
    min_remaining_equity: float = field(default_factory=lambda: _float("EDGE_FACTORY_MIN_REMAINING_EQUITY", 10.0))

    # ── Intraday Mode (V2 Add-On, OFF by default) ──────────
    intraday_enabled: bool = field(default_factory=lambda: _bool("EF_INTRADAY_ENABLED", False))
    intraday_rsi_bear: float = field(default_factory=lambda: _float("EF_INTRADAY_RSI_BEAR", 28.0))
    intraday_rsi_bull: float = field(default_factory=lambda: _float("EF_INTRADAY_RSI_BULL", 40.0))
    intraday_funding_buy_max: float = field(default_factory=lambda: _float("EF_INTRADAY_FUNDING_BUY_MAX", 0.00001))
    intraday_funding_danger: float = field(default_factory=lambda: _float("EF_INTRADAY_FUNDING_DANGER", 0.0002))
    intraday_tp_pct: float = field(default_factory=lambda: _float("EF_INTRADAY_TP_PCT", 0.045))
    intraday_sl_pct: float = field(default_factory=lambda: _float("EF_INTRADAY_SL_PCT", 0.03))
    intraday_time_stop_hours: int = field(default_factory=lambda: _int("EF_INTRADAY_TIME_STOP", 12))
    intraday_vol_halt_range: float = field(default_factory=lambda: _float("EF_INTRADAY_VOL_HALT", 0.05))
    intraday_liquidity_min: float = field(default_factory=lambda: _float("EF_INTRADAY_LIQUIDITY_MIN", 1e7))
    intraday_max_bullets_24h: int = field(default_factory=lambda: _int("EF_INTRADAY_MAX_BULLETS", 2))
    intraday_rung_pct: float = field(default_factory=lambda: _float("EF_INTRADAY_RUNG_PCT", 0.25))
    intraday_max_rungs: int = field(default_factory=lambda: _int("EF_INTRADAY_MAX_RUNGS", 4))
    intraday_chase_step_pct: float = field(default_factory=lambda: _float("EF_INTRADAY_CHASE_STEP", 0.0005))
    intraday_chase_steps: int = field(default_factory=lambda: _int("EF_INTRADAY_CHASE_STEPS", 3))
    intraday_chase_interval_sec: int = field(default_factory=lambda: _int("EF_INTRADAY_CHASE_INTERVAL", 60))
    intraday_max_cross_pct: float = field(default_factory=lambda: _float("EF_INTRADAY_MAX_CROSS", 0.002))

    def is_active(self) -> bool:
        return self.mode in {"paper", "live"}

    def is_live(self) -> bool:
        return self.mode == "live"

    def max_position_usd(self) -> float:
        return min(self.account_equity * self.max_position_pct, self.max_notional_per_trade)
