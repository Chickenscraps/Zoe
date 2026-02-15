"""Trade Scanner — profit-maximizing multi-coin edge engine.

Scans all coins, but ONLY trades the highest-conviction setups.
Every trade decision passes through:
  1. Universe filter (liquidity, spread, volume)
  2. Indicator validation (EMA, MACD, RSI, ATR, Bollinger, regime)
  3. Cost-aware edge filter (expected_profit > cost * safety_multiplier)
  4. Capital concentration (fewer, larger trades on best setups)
  5. Cooldown enforcement (no churn, no repeated entries)

CORE PRINCIPLES:
  - SELECTIVITY > COVERAGE: Trade ONLY the best setups
  - EDGE > ACTIVITY: If edge is unclear, DO NOTHING
  - COSTS ARE REAL: Fees + spread + slippage destroy weak signals
  - LIQUIDITY FIRST: Never trade illiquid pairs
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .indicators import (
    IndicatorEngine,
    IndicatorSnapshot,
    Regime,
    ROUND_TRIP_COST,
    TAKER_FEE_RATE,
    estimate_round_trip_cost,
    expected_profit_exceeds_cost,
    get_taker_fee,
    load_fee_config,
)
from services.position_sizer import PositionSizer

logger = logging.getLogger(__name__)

# ── Smart order type thresholds ──────────────────────────────────
SPREAD_MARKET_THRESHOLD = 0.05    # Below 0.05% spread → market order
SPREAD_MID_THRESHOLD = 0.15       # 0.05-0.15% → limit at mid
# Above 0.15% → limit 30% into spread from favorable side

# ── Defaults ────────────────────────────────────────────────────────
# Conservative defaults that prioritize profitability over activity

DEFAULT_MIN_SCORE = 65              # HIGH bar — only strong setups
DEFAULT_MAX_SPREAD_PCT = 0.30       # 0.30% max spread (tighter than before)
DEFAULT_MIN_VOLUME_24H = 50_000     # $50K min daily volume (was $10K)
DEFAULT_MAX_POSITIONS = 3           # Concentrate capital (was 5)
DEFAULT_MAX_NOTIONAL = 50.0         # Per trade
DEFAULT_MAX_EXPOSURE = 150.0        # Total across all positions (was 200)
DEFAULT_MOVER_WINDOW_MIN = 30       # Mover lookback
DEFAULT_TOP_N_WRITE = 50            # Dashboard display
DEFAULT_COOLDOWN_SECONDS = 600      # 10 min per-symbol cooldown (was 0)
DEFAULT_COST_SAFETY_MULT = 2.0      # Expected profit must exceed 2x costs
DEFAULT_MIN_ATR_PCT = 0.05          # Minimum volatility to trade (ATR as % of price)
DEFAULT_MAX_CHANGE_PCT = 12.0       # Reject extreme moves (was 15%)
DEFAULT_SCAN_INTERVAL = 120.0       # 2 minutes between scans (was 30s)


@dataclass
class ScoredCandidate:
    """A scored trade candidate with full indicator context."""
    symbol: str
    mid: float
    bid: float
    ask: float
    spread_pct: float
    volume_24h: float
    change_24h_pct: float
    vwap: float

    # Score components (0-100 total)
    momentum_score: float = 0.0     # 0-25: EMA alignment + MACD confirmation
    volume_score: float = 0.0       # 0-15: relative volume strength
    spread_score: float = 0.0       # 0-15: tighter = better
    trend_score: float = 0.0        # 0-20: regime clarity + trend strength
    mean_revert_score: float = 0.0  # 0-15: RSI extreme + z-score for reversals
    mover_score: float = 0.0        # 0-10: mover event bonus (scaled, not binary)

    # Indicator context
    regime: Regime = Regime.UNKNOWN
    rsi: float = 50.0
    atr_pct: float = 0.0
    macd_histogram: float = 0.0
    zscore: float = 0.0
    bb_squeeze: bool = False
    indicators_valid: bool = False

    # Cost model
    estimated_cost: float = 0.0     # Round-trip cost in USD
    expected_move_pct: float = 0.0  # ATR-based expected move
    edge_ratio: float = 0.0         # expected_profit / cost

    @property
    def total_score(self) -> float:
        return (
            self.momentum_score
            + self.volume_score
            + self.spread_score
            + self.trend_score
            + self.mean_revert_score
            + self.mover_score
        )

    @property
    def recommended_side(self) -> str:
        """Determine trade side based on regime + indicators."""
        if self.regime == Regime.TRENDING_UP:
            return "buy"
        if self.regime == Regime.TRENDING_DOWN:
            return "sell"
        if self.regime == Regime.MEAN_REVERTING:
            # Buy oversold, sell overbought
            if self.rsi < 30 or self.zscore < -1.5:
                return "buy"
            if self.rsi > 70 or self.zscore > 1.5:
                return "sell"
        # Follow short-term momentum
        return "buy" if self.macd_histogram > 0 else "sell"

    def score_breakdown(self) -> Dict[str, Any]:
        return {
            "momentum": round(self.momentum_score, 1),
            "volume": round(self.volume_score, 1),
            "spread": round(self.spread_score, 1),
            "trend": round(self.trend_score, 1),
            "mean_revert": round(self.mean_revert_score, 1),
            "mover": round(self.mover_score, 1),
            "total": round(self.total_score, 1),
            "regime": self.regime.value,
            "edge_ratio": round(self.edge_ratio, 2),
            "cost_usd": round(self.estimated_cost, 4),
        }

    def info_dict(self) -> Dict[str, Any]:
        return {
            "mid": self.mid,
            "bid": self.bid,
            "ask": self.ask,
            "spread_pct": round(self.spread_pct, 4),
            "volume_24h": round(self.volume_24h, 2),
            "change_24h_pct": round(self.change_24h_pct, 4),
            "vwap": round(self.vwap, 4),
            "side": self.recommended_side,
            "rsi": round(self.rsi, 1),
            "atr_pct": round(self.atr_pct, 4),
            "macd_hist": round(self.macd_histogram, 6),
            "zscore": round(self.zscore, 2),
            "regime": self.regime.value,
            "indicators_valid": self.indicators_valid,
        }


@dataclass
class TradeIntent:
    """A trade selected for submission with full context."""
    symbol: str
    side: str
    notional: float
    score: float
    strategy: str = "scanner"
    confidence: float = 0.0
    regime: str = "unknown"
    edge_ratio: float = 0.0
    atr_pct: float = 0.0
    rsi: float = 50.0
    reason: str = ""

    # Smart order type (market or limit)
    order_type: str = "market"
    limit_price: float | None = None

    # SL-aware sizing info
    sl_price: float = 0.0
    tp_price: float = 0.0
    qty: float = 0.0


class TradeScanner:
    """Profit-maximizing multi-coin trade scanner.

    Scans all available coins but applies strict filters to ensure
    only high-conviction, cost-positive trades are selected.
    """

    def __init__(
        self,
        supabase_client: Any,
        price_cache: Any = None,
        indicator_engine: IndicatorEngine | None = None,
        circuit_breaker: Any = None,
        position_sizer: PositionSizer | None = None,
        mode: str = "live",
        *,
        min_score: int = DEFAULT_MIN_SCORE,
        max_spread_pct: float = DEFAULT_MAX_SPREAD_PCT,
        min_volume_24h: float = DEFAULT_MIN_VOLUME_24H,
        max_positions: int = DEFAULT_MAX_POSITIONS,
        max_notional: float = DEFAULT_MAX_NOTIONAL,
        max_exposure: float = DEFAULT_MAX_EXPOSURE,
        mover_window_min: int = DEFAULT_MOVER_WINDOW_MIN,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        cost_safety_mult: float = DEFAULT_COST_SAFETY_MULT,
        dry_run: bool = False,
    ):
        self._sb = supabase_client
        self._price_cache = price_cache
        self._indicators = indicator_engine
        self._breaker = circuit_breaker
        self._sizer = position_sizer or PositionSizer.from_config()
        self._mode = mode

        # Load per-pair fee config on init
        load_fee_config()

        self.min_score = min_score
        self.max_spread_pct = max_spread_pct
        self.min_volume_24h = min_volume_24h
        self.max_positions = max_positions
        self.max_notional = max_notional
        self.max_exposure = max_exposure
        self.mover_window_min = mover_window_min
        self.cooldown_seconds = cooldown_seconds
        self.cost_safety_mult = cost_safety_mult
        self.dry_run = dry_run

        self._scan_count = 0
        self._last_candidates: List[ScoredCandidate] = []

        # Per-symbol cooldowns
        self._last_trade_ts: Dict[str, float] = {}

        # Stats
        self._total_trades_submitted = 0
        self._total_trades_blocked_cost = 0
        self._total_trades_blocked_cooldown = 0
        self._total_trades_blocked_regime = 0

    # ── Public API ──────────────────────────────────────────────────

    async def scan_candidates(self) -> List[ScoredCandidate]:
        """Fetch market data, compute indicators, score all coins."""
        self._scan_count += 1

        # 1. Fetch snapshots from Supabase
        snapshots = self._fetch_snapshots()
        if not snapshots:
            logger.debug("Scanner: no snapshots available")
            return []

        # 2. Fetch recent mover events
        mover_symbols = self._fetch_mover_symbols()

        # 3. Score each symbol with full indicator context
        candidates = []
        volumes = [s.get("volume_24h", 0) for s in snapshots if s.get("volume_24h", 0) > 0]
        vol_median = sorted(volumes)[len(volumes) // 2] if volumes else 1.0

        for snap in snapshots:
            candidate = self._score_symbol(snap, mover_symbols, vol_median)
            if candidate is not None:
                candidates.append(candidate)

        # 4. Sort by total score descending
        candidates.sort(key=lambda c: c.total_score, reverse=True)
        self._last_candidates = candidates

        above_threshold = sum(1 for c in candidates if c.total_score >= self.min_score)
        cost_positive = sum(1 for c in candidates if c.edge_ratio > self.cost_safety_mult)

        if self._scan_count % 5 == 1:  # Log every 5th scan
            logger.info(
                "Scanner #%d: %d scored, %d above threshold, %d cost-positive, top: %s (%.0f pts, regime=%s)",
                self._scan_count,
                len(candidates),
                above_threshold,
                cost_positive,
                candidates[0].symbol if candidates else "none",
                candidates[0].total_score if candidates else 0,
                candidates[0].regime.value if candidates else "n/a",
            )

        return candidates

    async def select_trades(
        self,
        candidates: List[ScoredCandidate],
        equity: float,
        open_positions: Dict[str, float],
    ) -> List[TradeIntent]:
        """Pick ONLY the highest-conviction, cost-positive trades."""
        intents: List[TradeIntent] = []
        total_new_exposure = 0.0
        existing_exposure = sum(open_positions.values())
        now = time.time()

        for c in candidates:
            # ── Gate 1: Minimum score ──
            if c.total_score < self.min_score:
                break  # Sorted descending

            # ── Gate 2: Indicators must be valid ──
            if not c.indicators_valid:
                continue

            # ── Gate 3: Regime must be clear ──
            if c.regime in (Regime.CHOPPY, Regime.UNKNOWN):
                self._total_trades_blocked_regime += 1
                continue

            # ── Gate 4: Cost-aware edge filter (CRITICAL) ──
            if c.edge_ratio < self.cost_safety_mult:
                self._total_trades_blocked_cost += 1
                continue

            # ── Gate 5: Already holding this symbol ──
            if c.symbol in open_positions:
                continue

            # ── Gate 6: Per-symbol cooldown ──
            last_trade = self._last_trade_ts.get(c.symbol, 0)
            if now - last_trade < self.cooldown_seconds:
                self._total_trades_blocked_cooldown += 1
                continue

            # ── Gate 7: Max positions ──
            if len(open_positions) + len(intents) >= self.max_positions:
                break

            # ── Gate 8: Total exposure cap ──
            if existing_exposure + total_new_exposure + self.max_notional > self.max_exposure:
                break

            # ── Gate 9: Circuit breaker ──
            if self._breaker and not self._breaker.can_trade(c.symbol, self.max_notional):
                continue

            # ── Determine side ──
            side = c.recommended_side

            # ── Compute TP/SL prices for position sizer ──
            if side == "buy":
                tp_price = c.mid * (1 + 0.045)  # 4.5% TP
                # SL: use ATR if available, else 3% hard stop
                if c.atr_pct > 0:
                    atr_sl = c.mid - (c.mid * c.atr_pct / 100 * 1.5)
                    hard_sl = c.mid * (1 - 0.03)
                    sl_price = max(atr_sl, hard_sl)  # Tighter of ATR vs hard
                else:
                    sl_price = c.mid * (1 - 0.03)
            else:
                tp_price = c.mid * (1 - 0.045)
                if c.atr_pct > 0:
                    atr_sl = c.mid + (c.mid * c.atr_pct / 100 * 1.5)
                    hard_sl = c.mid * (1 + 0.03)
                    sl_price = min(atr_sl, hard_sl)
                else:
                    sl_price = c.mid * (1 + 0.03)

            # ── SL-aware position sizing via PositionSizer ──
            sizing = self._sizer.calculate(
                equity=equity,
                entry_price=c.mid,
                sl_price=sl_price,
                tp_price=tp_price,
                score=int(c.total_score),
                volatility=c.atr_pct * 100 if c.atr_pct > 0 else None,
                bb_squeeze=c.bb_squeeze,
            )

            if sizing is None:
                continue  # Sizer rejected (too small, zero risk, etc.)

            # Cap at scanner's max_notional
            notional = min(sizing.notional_usd, self.max_notional)
            if notional < 5.0:
                continue  # Skip dust trades

            qty = notional / c.mid if c.mid > 0 else 0
            score_factor = min((c.total_score - self.min_score) / (100 - self.min_score), 1.0)
            score_factor = max(score_factor, 0.5)

            # ── Smart order type selection ──
            order_type = "market"
            limit_price = None

            if c.spread_pct < SPREAD_MARKET_THRESHOLD:
                # Tight spread: market order (cost difference negligible)
                order_type = "market"
            elif c.spread_pct < SPREAD_MID_THRESHOLD:
                # Medium spread: limit at mid (save ~0.15% maker vs taker)
                order_type = "limit"
                limit_price = round(c.mid, 8)
            else:
                # Wide spread: limit 30% into spread from favorable side
                order_type = "limit"
                if side == "buy":
                    limit_price = round(c.bid + (c.ask - c.bid) * 0.30, 8)
                else:
                    limit_price = round(c.ask - (c.ask - c.bid) * 0.30, 8)

            # Build reason string for logging
            reason = (
                f"score={c.total_score:.0f} regime={c.regime.value} "
                f"RSI={c.rsi:.0f} MACD_H={c.macd_histogram:.6f} "
                f"ATR%={c.atr_pct:.3f} edge={c.edge_ratio:.1f}x "
                f"spread={c.spread_pct:.3f}% order={order_type}"
                f"{f' lim=${limit_price:.2f}' if limit_price else ''}"
                f" sizing={sizing.reason}"
            )

            intent = TradeIntent(
                symbol=c.symbol,
                side=side,
                notional=round(notional, 2),
                score=c.total_score,
                strategy="scanner",
                confidence=score_factor,
                regime=c.regime.value,
                edge_ratio=c.edge_ratio,
                atr_pct=c.atr_pct,
                rsi=c.rsi,
                reason=reason,
                order_type=order_type,
                limit_price=limit_price,
                sl_price=round(sl_price, 8),
                tp_price=round(tp_price, 8),
                qty=round(qty, 8),
            )

            if self.dry_run:
                logger.info(
                    "[DRY RUN] Would trade: %s %s $%.2f (%s) — %s",
                    side.upper(), c.symbol, notional, order_type, reason,
                )
            else:
                intents.append(intent)
                total_new_exposure += notional
                self._last_trade_ts[c.symbol] = now
                self._total_trades_submitted += 1

        if intents:
            logger.info(
                "Scanner: selected %d trades (new=$%.2f, existing=$%.2f, equity=$%.2f)",
                len(intents), total_new_exposure, existing_exposure, equity,
            )

        return intents

    async def write_candidate_scans(self, candidates: List[ScoredCandidate]) -> None:
        """Write top N candidates to candidate_scans for dashboard display."""
        if not self._sb or not candidates:
            return

        top = candidates[:DEFAULT_TOP_N_WRITE]
        now = datetime.now(timezone.utc).isoformat()
        rows = []

        for c in top:
            # candidate_scans table only has: symbol, score, mode, created_at
            # (score_breakdown, info, recommended_strategy columns don't exist)
            rows.append({
                "symbol": c.symbol,
                "score": round(c.total_score, 1),
                "mode": self._mode,
                "created_at": now,
            })

        try:
            self._sb.table("candidate_scans").insert(rows).execute()
            logger.debug("Scanner: wrote %d candidates to candidate_scans", len(rows))
        except Exception as e:
            logger.warning("Scanner: candidate_scans write failed: %s", e)

    def get_stats(self) -> Dict[str, Any]:
        """Return scanner performance stats."""
        return {
            "scan_count": self._scan_count,
            "trades_submitted": self._total_trades_submitted,
            "blocked_cost": self._total_trades_blocked_cost,
            "blocked_cooldown": self._total_trades_blocked_cooldown,
            "blocked_regime": self._total_trades_blocked_regime,
            "symbols_tracked": self._indicators.tracked_symbols if self._indicators else 0,
        }

    # ── Private helpers ─────────────────────────────────────────────

    def _fetch_snapshots(self) -> List[Dict[str, Any]]:
        """Fetch latest market snapshots from both focus and scout tables."""
        all_snaps: List[Dict[str, Any]] = []

        # Focus: high-priority, 1s updates
        try:
            resp = self._sb.table("market_snapshot_focus").select(
                "symbol, bid, ask, mid, spread_pct, volume_24h, change_24h_pct, vwap, updated_at"
            ).gt("mid", 0).execute()
            if resp.data:
                all_snaps.extend(resp.data)
        except Exception as e:
            logger.warning("Scanner: focus snapshot fetch failed: %s", e)

        # Scout: broader universe, 30s updates
        focus_symbols = {s["symbol"] for s in all_snaps}
        try:
            resp = self._sb.table("market_snapshot_scout").select(
                "symbol, bid, ask, mid, spread_pct, volume_24h, change_24h_pct, updated_at"
            ).gt("mid", 0).execute()
            if resp.data:
                for row in resp.data:
                    if row["symbol"] not in focus_symbols:
                        row.setdefault("vwap", 0)
                        all_snaps.append(row)
        except Exception as e:
            logger.warning("Scanner: scout snapshot fetch failed: %s", e)

        return all_snaps

    def _fetch_mover_symbols(self) -> Dict[str, float]:
        """Fetch symbols that triggered mover events, with magnitude."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=self.mover_window_min)).isoformat()
        try:
            resp = self._sb.table("mover_events").select(
                "symbol, magnitude"
            ).gte("detected_at", cutoff).execute()
            if resp.data:
                # Take max magnitude per symbol
                movers: Dict[str, float] = {}
                for row in resp.data:
                    sym = row["symbol"]
                    mag = float(row.get("magnitude", 0))
                    movers[sym] = max(movers.get(sym, 0), mag)
                return movers
        except Exception as e:
            logger.debug("Scanner: mover events fetch failed: %s", e)
        return {}

    def _score_symbol(
        self,
        snap: Dict[str, Any],
        mover_symbols: Dict[str, float],
        vol_median: float,
    ) -> Optional[ScoredCandidate]:
        """Score a single symbol using indicators + market data."""
        symbol = snap.get("symbol", "")
        mid = float(snap.get("mid", 0))
        bid = float(snap.get("bid", 0))
        ask = float(snap.get("ask", 0))
        spread_pct = float(snap.get("spread_pct", 0))
        volume_24h = float(snap.get("volume_24h", 0))
        change_24h_pct = float(snap.get("change_24h_pct", 0))
        vwap = float(snap.get("vwap", 0))

        if mid <= 0:
            return None

        # ── Hard filters (STRICT) ──
        if spread_pct > self.max_spread_pct:
            return None
        if volume_24h < self.min_volume_24h:
            return None
        if abs(change_24h_pct) > DEFAULT_MAX_CHANGE_PCT:
            return None

        # ── Get indicator snapshot ──
        ind: Optional[IndicatorSnapshot] = None
        if self._indicators:
            ind = self._indicators.snapshot(symbol)

        candidate = ScoredCandidate(
            symbol=symbol, mid=mid, bid=bid, ask=ask,
            spread_pct=spread_pct, volume_24h=volume_24h,
            change_24h_pct=change_24h_pct, vwap=vwap,
        )

        # Populate indicator context
        if ind and ind.is_valid():
            candidate.indicators_valid = True
            candidate.regime = ind.regime
            candidate.rsi = ind.rsi
            candidate.atr_pct = ind.atr_pct
            candidate.macd_histogram = ind.macd_histogram
            candidate.zscore = ind.zscore
            candidate.bb_squeeze = ind.bb_squeeze

        # ── Momentum score (0-25) ──
        # Uses REAL indicators: EMA alignment + MACD confirmation
        if ind and ind.is_valid():
            # EMA alignment (0-10)
            if ind.ema_fast > 0 and ind.ema_slow > 0:
                ema_sep = abs(ind.ema_fast - ind.ema_slow) / ind.ema_slow * 100
                candidate.momentum_score += min(10.0, ema_sep * 20)

            # MACD histogram strength (0-10)
            if ind.macd_histogram != 0 and mid > 0:
                macd_strength = abs(ind.macd_histogram) / mid * 10000
                candidate.momentum_score += min(10.0, macd_strength * 2)

            # EMA slope direction aligns with MACD (0-5 bonus)
            if (ind.ema_slope > 0 and ind.macd_histogram > 0) or \
               (ind.ema_slope < 0 and ind.macd_histogram < 0):
                candidate.momentum_score += 5.0
        else:
            # Fallback: use 24h change as rough proxy (much weaker signal)
            abs_change = abs(change_24h_pct)
            if 1.0 <= abs_change <= 8.0:
                candidate.momentum_score = min(10.0, abs_change * 1.5)

        # ── Volume score (0-15) ──
        if vol_median > 0 and volume_24h > 0:
            vol_ratio = volume_24h / vol_median
            candidate.volume_score = min(15.0, vol_ratio * 3)

        # ── Spread score (0-15) ──
        if spread_pct <= 0.02:
            candidate.spread_score = 15.0
        elif spread_pct <= 0.05:
            candidate.spread_score = 12.0
        elif spread_pct <= 0.10:
            candidate.spread_score = 9.0
        elif spread_pct <= 0.20:
            candidate.spread_score = 5.0
        elif spread_pct <= 0.30:
            candidate.spread_score = 2.0

        # ── Trend score (0-20) ──
        if ind and ind.is_valid():
            # Regime clarity bonus
            if ind.regime in (Regime.TRENDING_UP, Regime.TRENDING_DOWN):
                candidate.trend_score += 12.0
            elif ind.regime == Regime.MEAN_REVERTING:
                candidate.trend_score += 8.0
            elif ind.regime == Regime.CHOPPY:
                candidate.trend_score += 0.0  # NO bonus for choppy
            # Trend strength bonus (0-8)
            candidate.trend_score += min(8.0, ind.trend_strength * 16)

        # ── Mean reversion score (0-15) ──
        if ind and ind.is_valid() and ind.regime == Regime.MEAN_REVERTING:
            # RSI extremity (0-8)
            if ind.rsi < 25:
                candidate.mean_revert_score += 8.0
            elif ind.rsi < 30:
                candidate.mean_revert_score += 6.0
            elif ind.rsi > 75:
                candidate.mean_revert_score += 8.0
            elif ind.rsi > 70:
                candidate.mean_revert_score += 6.0

            # Z-score extremity (0-7)
            abs_z = abs(ind.zscore)
            if abs_z > 2.5:
                candidate.mean_revert_score += 7.0
            elif abs_z > 2.0:
                candidate.mean_revert_score += 5.0
            elif abs_z > 1.5:
                candidate.mean_revert_score += 3.0

        # ── Mover bonus (0-10, SCALED by magnitude) ──
        mover_mag = mover_symbols.get(symbol, 0)
        if mover_mag > 0:
            candidate.mover_score = min(10.0, mover_mag * 2)

        # ── Cost model (per-pair fee-aware) ──
        # Determine likely order type for fee estimation
        likely_order_type = "market"
        if spread_pct > SPREAD_MARKET_THRESHOLD:
            likely_order_type = "limit"  # Will use maker fee for entry

        candidate.estimated_cost = estimate_round_trip_cost(
            self.max_notional, spread_pct,
            symbol=symbol, order_type=likely_order_type,
        )
        # Expected move: use ATR if available, else use fraction of 24h change
        if ind and ind.atr_pct > 0:
            candidate.expected_move_pct = ind.atr_pct
        else:
            candidate.expected_move_pct = abs(change_24h_pct) * 0.1  # Very conservative

        if candidate.estimated_cost > 0:
            expected_profit = self.max_notional * (candidate.expected_move_pct / 100)
            candidate.edge_ratio = expected_profit / candidate.estimated_cost
        else:
            candidate.edge_ratio = 0

        return candidate

    # ── Backward-compatible properties ──

    @property
    def _scan_count_value(self) -> int:
        return self._scan_count
