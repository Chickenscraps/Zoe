"""Technical Indicator Engine — rolling OHLC history + computed indicators.

All indicators are computed from a rolling price history fed by PriceCache.
Each symbol maintains its own deque of (timestamp, mid) observations.

Indicators computed:
  - EMA (any period): Exponential Moving Average
  - MACD (fast/slow/signal): histogram + signal line
  - RSI (14-period Wilder): Relative Strength Index
  - ATR (14-period): Average True Range (approximated from mid-price changes)
  - Bollinger Bands (20, 2σ): squeeze detection
  - Z-Score: deviation from rolling mean in standard deviations
  - Regime: TRENDING / MEAN_REVERTING / CHOPPY / UNKNOWN

Cost model constants for Kraken:
  - Taker fee: 0.40% (40 bps) per side
  - Maker fee: 0.25% (25 bps) per side
  - We assume taker for conservatism
"""
from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Cost Constants (defaults — overridden by config.yaml fees section) ──
TAKER_FEE_RATE = 0.0040   # 0.40% per side (Kraken intermediate tier)
MAKER_FEE_RATE = 0.0025   # 0.25% per side
SLIPPAGE_ESTIMATE = 0.001  # 0.10% estimated slippage
ROUND_TRIP_COST = (TAKER_FEE_RATE * 2) + SLIPPAGE_ESTIMATE  # ~0.90% total

# Per-pair fee overrides loaded from config.yaml
_FEE_OVERRIDES: dict[str, dict[str, float]] = {}
_FEE_CONFIG_LOADED = False


def load_fee_config() -> None:
    """Load fee schedule from config.yaml (called once at startup)."""
    global TAKER_FEE_RATE, MAKER_FEE_RATE, SLIPPAGE_ESTIMATE, ROUND_TRIP_COST
    global _FEE_OVERRIDES, _FEE_CONFIG_LOADED

    if _FEE_CONFIG_LOADED:
        return

    try:
        import yaml
        from pathlib import Path

        config_path = Path(__file__).resolve().parents[2] / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}

            fees = cfg.get("fees", {})
            if fees:
                default_taker = fees.get("default_taker_bps", 40)
                default_maker = fees.get("default_maker_bps", 25)
                slippage = fees.get("slippage_bps", 10)

                TAKER_FEE_RATE = default_taker / 10_000
                MAKER_FEE_RATE = default_maker / 10_000
                SLIPPAGE_ESTIMATE = slippage / 10_000
                ROUND_TRIP_COST = (TAKER_FEE_RATE * 2) + SLIPPAGE_ESTIMATE

                # Load per-pair overrides
                for symbol, override in fees.get("pair_overrides", {}).items():
                    _FEE_OVERRIDES[symbol] = {
                        "taker": override.get("taker_bps", default_taker) / 10_000,
                        "maker": override.get("maker_bps", default_maker) / 10_000,
                    }

                logger.info(
                    "Fee config loaded: taker=%.2f%% maker=%.2f%% slippage=%.2f%% overrides=%d pairs",
                    TAKER_FEE_RATE * 100, MAKER_FEE_RATE * 100, SLIPPAGE_ESTIMATE * 100, len(_FEE_OVERRIDES),
                )
    except Exception as e:
        logger.debug("Fee config load failed (using defaults): %s", e)
    finally:
        _FEE_CONFIG_LOADED = True


def get_taker_fee(symbol: str = "") -> float:
    """Get taker fee rate for a specific symbol (falls back to default)."""
    load_fee_config()
    if symbol and symbol in _FEE_OVERRIDES:
        return _FEE_OVERRIDES[symbol]["taker"]
    return TAKER_FEE_RATE


def get_maker_fee(symbol: str = "") -> float:
    """Get maker fee rate for a specific symbol (falls back to default)."""
    load_fee_config()
    if symbol and symbol in _FEE_OVERRIDES:
        return _FEE_OVERRIDES[symbol]["maker"]
    return MAKER_FEE_RATE

# ── Indicator defaults ───────────────────────────────────────────
EMA_FAST = 12
EMA_SLOW = 26
MACD_SIGNAL = 9
RSI_PERIOD = 14
ATR_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2.0
ZSCORE_PERIOD = 20

# Minimum observations needed before indicators are valid
MIN_OBSERVATIONS_EMA = 30     # ~15 min at 30s intervals
MIN_OBSERVATIONS_MACD = 40    # need slow EMA + signal EMA
MIN_OBSERVATIONS_RSI = 20
MIN_OBSERVATIONS_ATR = 20
MIN_OBSERVATIONS_BB = 25

# Max history per symbol (at 30s intervals, 240 = 2 hours)
MAX_HISTORY_SIZE = 480  # 4 hours of 30s ticks


class Regime(Enum):
    """Market regime classification."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    MEAN_REVERTING = "mean_reverting"
    CHOPPY = "choppy"
    UNKNOWN = "unknown"


@dataclass
class IndicatorSnapshot:
    """Complete indicator state for a symbol at a point in time."""
    symbol: str
    mid: float
    timestamp: float
    observations: int

    # EMAs
    ema_fast: float = 0.0       # 12-period EMA
    ema_slow: float = 0.0       # 26-period EMA
    ema_slope: float = 0.0      # (ema_fast - prev_ema_fast) / prev_ema_fast * 100

    # MACD
    macd_line: float = 0.0      # ema_fast - ema_slow
    macd_signal: float = 0.0    # 9-period EMA of macd_line
    macd_histogram: float = 0.0  # macd_line - macd_signal

    # RSI
    rsi: float = 50.0

    # ATR (approximated from mid-price absolute changes)
    atr: float = 0.0
    atr_pct: float = 0.0       # ATR as % of price

    # Bollinger Bands
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    bb_mid: float = 0.0        # 20-period SMA
    bb_width_pct: float = 0.0  # (upper - lower) / mid * 100
    bb_squeeze: bool = False    # width < historical average * 0.5

    # Z-Score
    zscore: float = 0.0        # (price - mean) / std

    # Regime
    regime: Regime = Regime.UNKNOWN

    # Derived signals
    momentum_bullish: bool = False  # EMA fast > slow AND MACD histogram > 0
    momentum_bearish: bool = False  # EMA fast < slow AND MACD histogram < 0
    rsi_oversold: bool = False      # RSI < 30
    rsi_overbought: bool = False    # RSI > 70
    trend_strength: float = 0.0     # 0-1 how strong the trend is

    def is_valid(self) -> bool:
        """Whether enough data exists for reliable signals."""
        return self.observations >= MIN_OBSERVATIONS_MACD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ema_fast": round(self.ema_fast, 4),
            "ema_slow": round(self.ema_slow, 4),
            "ema_slope": round(self.ema_slope, 4),
            "macd_line": round(self.macd_line, 6),
            "macd_signal": round(self.macd_signal, 6),
            "macd_histogram": round(self.macd_histogram, 6),
            "rsi": round(self.rsi, 1),
            "atr": round(self.atr, 6),
            "atr_pct": round(self.atr_pct, 4),
            "bb_upper": round(self.bb_upper, 4),
            "bb_lower": round(self.bb_lower, 4),
            "bb_width_pct": round(self.bb_width_pct, 4),
            "bb_squeeze": self.bb_squeeze,
            "zscore": round(self.zscore, 2),
            "regime": self.regime.value,
            "momentum_bullish": self.momentum_bullish,
            "momentum_bearish": self.momentum_bearish,
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
            "trend_strength": round(self.trend_strength, 3),
            "observations": self.observations,
            "valid": self.is_valid(),
        }


@dataclass
class _SymbolState:
    """Internal state tracking for a single symbol's indicators."""
    prices: deque = field(default_factory=lambda: deque(maxlen=MAX_HISTORY_SIZE))

    # EMA state (incrementally updated)
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    prev_ema_fast: float = 0.0
    ema_fast_initialized: bool = False
    ema_slow_initialized: bool = False

    # MACD signal EMA
    macd_signal_ema: float = 0.0
    macd_signal_initialized: bool = False
    macd_history: deque = field(default_factory=lambda: deque(maxlen=50))

    # RSI state (Wilder's smoothing)
    avg_gain: float = 0.0
    avg_loss: float = 0.0
    rsi_initialized: bool = False
    prev_price: float = 0.0

    # ATR state
    atr: float = 0.0
    atr_initialized: bool = False
    price_changes: deque = field(default_factory=lambda: deque(maxlen=ATR_PERIOD + 5))

    # Bollinger state
    bb_width_history: deque = field(default_factory=lambda: deque(maxlen=100))

    # Cooldown tracking
    last_trade_ts: float = 0.0
    last_trade_side: str = ""
    consecutive_no_trade: int = 0


class IndicatorEngine:
    """Computes technical indicators from streaming price data.

    Feed with update() on each WS tick or scanner cycle.
    Query with snapshot() to get complete indicator state.

    Usage:
        engine = IndicatorEngine()
        engine.update("BTC-USD", mid=70000.0)
        # ... many updates later ...
        snap = engine.snapshot("BTC-USD")
        if snap.is_valid() and snap.momentum_bullish:
            ...
    """

    def __init__(
        self,
        ema_fast: int = EMA_FAST,
        ema_slow: int = EMA_SLOW,
        macd_signal_period: int = MACD_SIGNAL,
        rsi_period: int = RSI_PERIOD,
        atr_period: int = ATR_PERIOD,
        bb_period: int = BB_PERIOD,
        bb_std: float = BB_STD,
    ):
        self._states: Dict[str, _SymbolState] = {}
        self._ema_fast_period = ema_fast
        self._ema_slow_period = ema_slow
        self._macd_signal_period = macd_signal_period
        self._rsi_period = rsi_period
        self._atr_period = atr_period
        self._bb_period = bb_period
        self._bb_std = bb_std

        # EMA multipliers (pre-computed)
        self._ema_fast_k = 2.0 / (ema_fast + 1)
        self._ema_slow_k = 2.0 / (ema_slow + 1)
        self._macd_signal_k = 2.0 / (macd_signal_period + 1)
        self._rsi_k = 1.0 / rsi_period

    def update(self, symbol: str, mid: float) -> None:
        """Feed a new price observation. Call on every tick."""
        if mid <= 0:
            return

        now = time.time()
        state = self._states.get(symbol)
        if state is None:
            state = _SymbolState()
            self._states[symbol] = state

        state.prices.append((now, mid))
        n = len(state.prices)

        # ── EMA updates ──
        if not state.ema_fast_initialized:
            if n >= self._ema_fast_period:
                # Initialize with SMA of first N prices
                prices = [p for _, p in list(state.prices)[-self._ema_fast_period:]]
                state.ema_fast = sum(prices) / len(prices)
                state.prev_ema_fast = state.ema_fast
                state.ema_fast_initialized = True
        else:
            state.prev_ema_fast = state.ema_fast
            state.ema_fast = mid * self._ema_fast_k + state.ema_fast * (1 - self._ema_fast_k)

        if not state.ema_slow_initialized:
            if n >= self._ema_slow_period:
                prices = [p for _, p in list(state.prices)[-self._ema_slow_period:]]
                state.ema_slow = sum(prices) / len(prices)
                state.ema_slow_initialized = True
        else:
            state.ema_slow = mid * self._ema_slow_k + state.ema_slow * (1 - self._ema_slow_k)

        # ── MACD ──
        if state.ema_fast_initialized and state.ema_slow_initialized:
            macd_line = state.ema_fast - state.ema_slow
            state.macd_history.append(macd_line)

            if not state.macd_signal_initialized:
                if len(state.macd_history) >= self._macd_signal_period:
                    state.macd_signal_ema = sum(list(state.macd_history)[-self._macd_signal_period:]) / self._macd_signal_period
                    state.macd_signal_initialized = True
            else:
                state.macd_signal_ema = macd_line * self._macd_signal_k + state.macd_signal_ema * (1 - self._macd_signal_k)

        # ── RSI (Wilder's smoothing) ──
        if state.prev_price > 0:
            change = mid - state.prev_price
            gain = max(change, 0)
            loss = max(-change, 0)

            if not state.rsi_initialized:
                # Need RSI_PERIOD changes to initialize
                if n > self._rsi_period:
                    # Initialize with SMA of gains/losses
                    recent = list(state.prices)[-self._rsi_period - 1:]
                    gains = []
                    losses = []
                    for i in range(1, len(recent)):
                        c = recent[i][1] - recent[i - 1][1]
                        gains.append(max(c, 0))
                        losses.append(max(-c, 0))
                    if gains:
                        state.avg_gain = sum(gains) / len(gains)
                        state.avg_loss = sum(losses) / len(losses)
                        state.rsi_initialized = True
            else:
                # Wilder's smoothing
                state.avg_gain = (state.avg_gain * (self._rsi_period - 1) + gain) / self._rsi_period
                state.avg_loss = (state.avg_loss * (self._rsi_period - 1) + loss) / self._rsi_period

        state.prev_price = mid

        # ── ATR (approximated from absolute mid-price changes) ──
        if n >= 2:
            prev_mid = state.prices[-2][1]
            abs_change = abs(mid - prev_mid)
            state.price_changes.append(abs_change)

            if not state.atr_initialized:
                if len(state.price_changes) >= self._atr_period:
                    state.atr = sum(list(state.price_changes)[-self._atr_period:]) / self._atr_period
                    state.atr_initialized = True
            else:
                # Wilder's smoothing for ATR
                state.atr = (state.atr * (self._atr_period - 1) + abs_change) / self._atr_period

    def snapshot(self, symbol: str) -> IndicatorSnapshot:
        """Get complete indicator snapshot for a symbol."""
        state = self._states.get(symbol)
        if state is None or len(state.prices) == 0:
            return IndicatorSnapshot(symbol=symbol, mid=0, timestamp=0, observations=0)

        mid = state.prices[-1][1]
        ts = state.prices[-1][0]
        n = len(state.prices)

        snap = IndicatorSnapshot(
            symbol=symbol, mid=mid, timestamp=ts, observations=n,
        )

        # ── EMAs ──
        if state.ema_fast_initialized:
            snap.ema_fast = state.ema_fast
        if state.ema_slow_initialized:
            snap.ema_slow = state.ema_slow
        if state.prev_ema_fast > 0:
            snap.ema_slope = (state.ema_fast - state.prev_ema_fast) / state.prev_ema_fast * 100

        # ── MACD ──
        if state.ema_fast_initialized and state.ema_slow_initialized:
            snap.macd_line = state.ema_fast - state.ema_slow
            if state.macd_signal_initialized:
                snap.macd_signal = state.macd_signal_ema
                snap.macd_histogram = snap.macd_line - snap.macd_signal

        # ── RSI ──
        if state.rsi_initialized:
            if state.avg_loss == 0:
                snap.rsi = 100.0
            else:
                rs = state.avg_gain / state.avg_loss
                snap.rsi = 100.0 - (100.0 / (1.0 + rs))
            snap.rsi_oversold = snap.rsi < 30
            snap.rsi_overbought = snap.rsi > 70

        # ── ATR ──
        if state.atr_initialized:
            snap.atr = state.atr
            snap.atr_pct = (state.atr / mid * 100) if mid > 0 else 0

        # ── Bollinger Bands ──
        if n >= self._bb_period:
            recent_prices = [p for _, p in list(state.prices)[-self._bb_period:]]
            sma = sum(recent_prices) / len(recent_prices)
            variance = sum((p - sma) ** 2 for p in recent_prices) / len(recent_prices)
            std = math.sqrt(variance)

            snap.bb_mid = sma
            snap.bb_upper = sma + self._bb_std * std
            snap.bb_lower = sma - self._bb_std * std
            snap.bb_width_pct = ((snap.bb_upper - snap.bb_lower) / mid * 100) if mid > 0 else 0

            # Track width history for squeeze detection
            state.bb_width_history.append(snap.bb_width_pct)
            if len(state.bb_width_history) > 20:
                avg_width = sum(state.bb_width_history) / len(state.bb_width_history)
                snap.bb_squeeze = snap.bb_width_pct < avg_width * 0.5

        # ── Z-Score ──
        if n >= ZSCORE_PERIOD:
            recent = [p for _, p in list(state.prices)[-ZSCORE_PERIOD:]]
            mean = sum(recent) / len(recent)
            variance = sum((p - mean) ** 2 for p in recent) / len(recent)
            std = math.sqrt(variance) if variance > 0 else 0.0001
            snap.zscore = (mid - mean) / std

        # ── Derived signals ──
        if state.ema_fast_initialized and state.ema_slow_initialized:
            snap.momentum_bullish = (
                snap.ema_fast > snap.ema_slow
                and snap.macd_histogram > 0
            )
            snap.momentum_bearish = (
                snap.ema_fast < snap.ema_slow
                and snap.macd_histogram < 0
            )

        # ── Trend strength (0-1) ──
        if state.ema_fast_initialized and state.ema_slow_initialized and mid > 0:
            ema_spread = abs(snap.ema_fast - snap.ema_slow) / mid
            macd_strength = min(abs(snap.macd_histogram) / (mid * 0.001), 1.0) if mid > 0 else 0
            rsi_extremity = abs(snap.rsi - 50) / 50  # 0 at RSI=50, 1 at RSI=0 or 100
            snap.trend_strength = min(1.0, (ema_spread * 200 + macd_strength + rsi_extremity) / 3)

        # ── Regime detection ──
        snap.regime = self._classify_regime(snap, state)

        return snap

    def _classify_regime(self, snap: IndicatorSnapshot, state: _SymbolState) -> Regime:
        """Classify market regime based on indicators."""
        if not snap.is_valid():
            return Regime.UNKNOWN

        n = len(state.prices)
        if n < MIN_OBSERVATIONS_MACD:
            return Regime.UNKNOWN

        # Check for trending: strong EMA separation + consistent MACD
        ema_aligned_bull = snap.ema_fast > snap.ema_slow and snap.macd_histogram > 0
        ema_aligned_bear = snap.ema_fast < snap.ema_slow and snap.macd_histogram < 0
        strong_trend = snap.trend_strength > 0.3

        if ema_aligned_bull and strong_trend:
            return Regime.TRENDING_UP
        if ema_aligned_bear and strong_trend:
            return Regime.TRENDING_DOWN

        # Check for mean-reverting: RSI extreme + Z-score extreme + low trend strength
        is_mean_reverting = (
            snap.trend_strength < 0.2
            and (abs(snap.zscore) > 1.5 or snap.rsi_oversold or snap.rsi_overbought)
        )
        if is_mean_reverting:
            return Regime.MEAN_REVERTING

        # Check for choppy: low trend strength + oscillating MACD
        if n >= 20:
            recent_macd = list(state.macd_history)[-20:] if len(state.macd_history) >= 20 else list(state.macd_history)
            if len(recent_macd) >= 10:
                sign_changes = sum(
                    1 for i in range(1, len(recent_macd))
                    if (recent_macd[i] > 0) != (recent_macd[i-1] > 0)
                )
                # Many sign changes = choppy
                if sign_changes >= 4 and snap.trend_strength < 0.2:
                    return Regime.CHOPPY

        return Regime.UNKNOWN

    def get_cooldown_state(self, symbol: str) -> tuple[float, str]:
        """Get last trade time and side for cooldown checks."""
        state = self._states.get(symbol)
        if state is None:
            return (0.0, "")
        return (state.last_trade_ts, state.last_trade_side)

    def record_trade(self, symbol: str, side: str) -> None:
        """Record that a trade was executed (for cooldown tracking)."""
        state = self._states.get(symbol)
        if state is None:
            state = _SymbolState()
            self._states[symbol] = state
        state.last_trade_ts = time.time()
        state.last_trade_side = side

    @property
    def tracked_symbols(self) -> int:
        return len(self._states)


def estimate_round_trip_cost(
    notional: float,
    spread_pct: float = 0.0,
    symbol: str = "",
    order_type: str = "market",
) -> float:
    """Estimate total round-trip cost for a trade.

    Returns dollar cost including:
      - Trading fees per side (taker or maker depending on order_type)
      - Half the current spread (entry cost)
      - Slippage estimate

    Uses per-pair fee overrides from config.yaml if available.
    """
    load_fee_config()

    # Use maker fee for limit orders, taker for market
    if order_type == "limit":
        entry_fee_rate = get_maker_fee(symbol)
        exit_fee_rate = get_taker_fee(symbol)  # exit is often taker (TP may be maker)
    else:
        entry_fee_rate = get_taker_fee(symbol)
        exit_fee_rate = get_taker_fee(symbol)

    fee_cost = notional * (entry_fee_rate + exit_fee_rate)
    spread_cost = notional * (spread_pct / 100) * 0.5  # half-spread on entry
    slippage_cost = notional * SLIPPAGE_ESTIMATE
    return fee_cost + spread_cost + slippage_cost


def expected_profit_exceeds_cost(
    notional: float,
    expected_move_pct: float,
    spread_pct: float = 0.0,
    safety_multiplier: float = 2.0,
    symbol: str = "",
    order_type: str = "market",
) -> tuple[bool, float, float]:
    """Check if expected profit exceeds cost with safety margin.

    Uses per-pair fee rates when symbol is provided.
    Returns (passes, expected_profit, total_cost).
    """
    expected_profit = notional * (expected_move_pct / 100)
    total_cost = estimate_round_trip_cost(notional, spread_pct, symbol=symbol, order_type=order_type)
    passes = expected_profit > total_cost * safety_multiplier
    return (passes, expected_profit, total_cost)
