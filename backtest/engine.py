"""
Backtest Engine — walk-forward simulation for the bounce catcher.

Feeds historical candles one-by-one through the BounceCatcher state machine,
simulates entries/exits with pessimistic fills, and tracks comprehensive
performance metrics.

Usage::

    from backtest.engine import BacktestEngine
    from backtest.data_loader import load_csv_candles

    df = load_csv_candles("btc_15m.csv")
    engine = BacktestEngine(starting_equity=2000)
    results = engine.run(df, symbol="BTC-USD")
    results.print_summary()
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from bounce.bounce_catcher import BounceCatcher
from bounce.config import BounceConfig
from bounce.entry_planner import TradeIntent
from bounce.exit_planner import compute_exit_plan, check_exit, ExitPlan, ExitSignal
from services.position_sizer import PositionSizer

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Record of a single simulated trade."""
    symbol: str
    entry_price: float
    entry_time: datetime
    exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    exit_trigger: str = ""
    notional: float = 0.0
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    score: int = 0
    r_multiple: float = 0.0
    risk_usd: float = 0.0
    sl_price: float = 0.0
    tp_price: float = 0.0
    duration_minutes: int = 0

    @property
    def is_win(self) -> bool:
        return self.pnl > 0

    @property
    def is_loss(self) -> bool:
        return self.pnl < 0


@dataclass
class BacktestResults:
    """Comprehensive backtest metrics."""
    symbol: str
    timeframe: str
    period_start: str
    period_end: str
    total_candles: int

    # Trade stats
    trades: List[Trade] = field(default_factory=list)
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    scratches: int = 0

    # P&L
    total_pnl: float = 0.0
    avg_pnl_per_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    profit_factor: float = 0.0

    # Risk
    win_rate: float = 0.0
    expectancy: float = 0.0
    avg_r_multiple: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_usd: float = 0.0
    sharpe_ratio: float = 0.0

    # Timing
    avg_hold_minutes: float = 0.0
    max_hold_minutes: float = 0.0

    # Equity curve
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)

    # Exit breakdown
    exits_by_trigger: Dict[str, int] = field(default_factory=dict)

    # Capitulations detected vs trades taken
    capitulations_detected: int = 0
    intents_emitted: int = 0
    intents_blocked: int = 0

    def print_summary(self) -> str:
        """Print a formatted performance summary."""
        lines = [
            "",
            "=" * 60,
            f"  BACKTEST RESULTS: {self.symbol} ({self.timeframe})",
            f"  Period: {self.period_start} to {self.period_end}",
            f"  Candles: {self.total_candles:,}",
            "=" * 60,
            "",
            f"  Trades:          {self.total_trades}",
            f"  Wins:            {self.wins} ({self.win_rate:.1f}%)",
            f"  Losses:          {self.losses}",
            f"  Scratches:       {self.scratches}",
            "",
            f"  Total P&L:       ${self.total_pnl:,.2f}",
            f"  Avg P&L/Trade:   ${self.avg_pnl_per_trade:,.2f}",
            f"  Avg Win:         ${self.avg_win:,.2f}",
            f"  Avg Loss:        ${self.avg_loss:,.2f}",
            f"  Largest Win:     ${self.largest_win:,.2f}",
            f"  Largest Loss:    ${self.largest_loss:,.2f}",
            f"  Profit Factor:   {self.profit_factor:.2f}",
            "",
            f"  Win Rate:        {self.win_rate:.1f}%",
            f"  Expectancy:      ${self.expectancy:,.2f}",
            f"  Avg R-Multiple:  {self.avg_r_multiple:.2f}R",
            f"  Sharpe Ratio:    {self.sharpe_ratio:.2f}",
            "",
            f"  Max Drawdown:    ${self.max_drawdown_usd:,.2f} ({self.max_drawdown_pct:.1f}%)",
            f"  Avg Hold Time:   {self.avg_hold_minutes:.0f} min",
            f"  Max Hold Time:   {self.max_hold_minutes:.0f} min",
            "",
            "  Exit Breakdown:",
        ]
        for trigger, count in sorted(self.exits_by_trigger.items()):
            lines.append(f"    {trigger:15s} {count}")
        lines += [
            "",
            f"  Detections:      {self.capitulations_detected} capitulations",
            f"  Intents:         {self.intents_emitted} emitted, {self.intents_blocked} blocked",
            "=" * 60,
        ]
        text = "\n".join(lines)
        print(text)
        return text


class BacktestEngine:
    """
    Walk-forward backtester for the bounce catcher.

    Parameters
    ----------
    starting_equity : float
        Initial account balance.
    config : BounceConfig, optional
        Bounce catcher config. Uses default if not provided.
    sizer : PositionSizer, optional
        Position sizer. Creates from config if not provided.
    slippage_bps : float
        Slippage in basis points (default 10bps = 0.1%).
    fee_bps : float
        Fee in basis points per side (default 5bps).
    """

    def __init__(
        self,
        starting_equity: float = 2000.0,
        config: Optional[BounceConfig] = None,
        sizer: Optional[PositionSizer] = None,
        slippage_bps: float = 10.0,
        fee_bps: float = 5.0,
    ):
        self.starting_equity = starting_equity
        self.slippage_bps = slippage_bps
        self.fee_bps = fee_bps

        # Config — default from config.yaml or passed
        if config is None:
            import yaml
            try:
                with open("config.yaml", "r") as f:
                    raw = yaml.safe_load(f) or {}
                config = BounceConfig.from_dict(raw.get("bounce", {}))
            except Exception:
                config = BounceConfig()
        # Force enabled for backtest (we want intents)
        config.enabled = True
        self.config = config

        # Position sizer
        self.sizer = sizer or PositionSizer.from_config()

    def run(
        self,
        df: pd.DataFrame,
        symbol: str = "BTC-USD",
        timeframe: str = "15m",
        df_1h: Optional[pd.DataFrame] = None,
    ) -> BacktestResults:
        """
        Run the backtest on historical OHLCV data.

        Parameters
        ----------
        df : pd.DataFrame
            Must have columns: open, high, low, close, volume.
            Index should be DatetimeIndex or have a 'timestamp' column.
        symbol : str
            Trading symbol.
        timeframe : str
            Candle timeframe (for results labeling).
        df_1h : pd.DataFrame, optional
            1h candles for multi-timeframe context.

        Returns
        -------
        BacktestResults
        """
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            if "timestamp" in df.columns:
                df.index = pd.to_datetime(df["timestamp"])
            elif "date" in df.columns:
                df.index = pd.to_datetime(df["date"])

        # Ensure required columns
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            raise ValueError(f"DataFrame missing columns: {required - set(df.columns)}")

        # Initialize bounce catcher (no DB — in-memory only)
        catcher = BounceCatcher(self.config, db=None)

        # State
        equity = self.starting_equity
        peak_equity = equity
        max_dd_usd = 0.0
        max_dd_pct = 0.0
        trades: List[Trade] = []
        equity_curve: List[Dict[str, Any]] = []
        current_trade: Optional[_OpenTrade] = None
        capitulations = 0
        intents_emitted = 0
        intents_blocked = 0

        # Minimum window for indicators
        min_window = max(self.config.atr_len + 5, self.config.vol_ma_len + 5, 30)

        for i in range(min_window, len(df)):
            # Sliding window of candles
            window = df.iloc[max(0, i - 200): i + 1]
            candle = df.iloc[i]
            candle_time = df.index[i]
            if hasattr(candle_time, "to_pydatetime"):
                candle_time = candle_time.to_pydatetime()
            if candle_time.tzinfo is None:
                candle_time = candle_time.replace(tzinfo=timezone.utc)

            current_price = float(candle["close"])

            # ── Check exit for active trade ────────────────────────
            if current_trade is not None:
                # Check against candle range (high/low) for more accurate sim
                # SL/panic triggers on low, TP triggers on high
                candle_low = float(candle["low"])
                candle_high = float(candle["high"])

                exit_signal = None

                # Check panic/SL against low
                if candle_low <= current_trade.exit_plan.panic_price:
                    exit_signal = ExitSignal(
                        trigger="panic",
                        target_price=current_trade.exit_plan.panic_price,
                        execution_mode="aggressive_chase",
                    )
                elif candle_low <= current_trade.exit_plan.sl_price:
                    exit_signal = ExitSignal(
                        trigger="sl",
                        target_price=current_trade.exit_plan.sl_price,
                        execution_mode="marketable_limit",
                    )
                # Check TP against high
                elif candle_high >= current_trade.exit_plan.tp_price:
                    exit_signal = ExitSignal(
                        trigger="tp",
                        target_price=current_trade.exit_plan.tp_price,
                        execution_mode="marketable_limit",
                    )
                # Check time stop
                elif candle_time >= current_trade.exit_plan.time_stop_at:
                    exit_signal = ExitSignal(
                        trigger="time_stop",
                        target_price=current_price,
                        execution_mode="marketable_limit",
                    )

                if exit_signal:
                    # Apply slippage to exit
                    exit_price = self._apply_slippage(exit_signal.target_price, "sell")
                    fee = current_trade.notional * (self.fee_bps / 10000)

                    pnl = (exit_price - current_trade.entry_price) * current_trade.quantity - fee
                    pnl_pct = pnl / current_trade.notional if current_trade.notional > 0 else 0
                    risk_per_unit = abs(current_trade.entry_price - current_trade.exit_plan.sl_price)
                    r_mult = (exit_price - current_trade.entry_price) / risk_per_unit if risk_per_unit > 0 else 0

                    hold_mins = int((candle_time - current_trade.entry_time).total_seconds() / 60)

                    trade = Trade(
                        symbol=symbol,
                        entry_price=current_trade.entry_price,
                        entry_time=current_trade.entry_time,
                        exit_price=exit_price,
                        exit_time=candle_time,
                        exit_trigger=exit_signal.trigger,
                        notional=current_trade.notional,
                        quantity=current_trade.quantity,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        score=current_trade.score,
                        r_multiple=r_mult,
                        risk_usd=current_trade.risk_usd,
                        sl_price=current_trade.exit_plan.sl_price,
                        tp_price=current_trade.exit_plan.tp_price,
                        duration_minutes=hold_mins,
                    )
                    trades.append(trade)
                    equity += pnl
                    current_trade = None

            # ── Feed candle to bounce catcher ──────────────────────
            if current_trade is None:
                # Build minimal indicators
                indicators = self._compute_indicators(window)

                # Build minimal market state
                market_state = {
                    "bid": current_price * 0.9999,
                    "ask": current_price * 1.0001,
                    "spread_pct": 0.0002,
                    "range_24h_pct": 0.02,
                }

                intent = catcher.process_tick(
                    symbol, window, None, indicators, market_state,
                )

                # Track state for metrics
                ss = catcher._get_state(symbol)
                if ss.state == "CAPITULATION_DETECTED" and not getattr(ss, "_counted_cap", False):
                    capitulations += 1
                    ss._counted_cap = True
                elif ss.state == "IDLE":
                    ss._counted_cap = False

                if intent is not None:
                    intents_emitted += 1
                    # Size the position
                    sizing = self.sizer.calculate(
                        equity=equity,
                        entry_price=intent.entry_price,
                        sl_price=intent.sl_price,
                        tp_price=intent.tp_price,
                        score=intent.score,
                    )

                    if sizing is None:
                        intents_blocked += 1
                    else:
                        # Enter trade with slippage
                        fill_price = self._apply_slippage(intent.entry_price, "buy")
                        entry_fee = sizing.notional_usd * (self.fee_bps / 10000)
                        equity -= entry_fee  # entry fee

                        exit_plan = compute_exit_plan(
                            fill_price,
                            float(ss.cap_metrics.get("atr", 0)),
                            float(ss.cap_candle_dict.get("low", 0)),
                            tp_pct=self.config.execution.tp_pct,
                            sl_atr_mult=self.config.execution.sl_atr_mult,
                            sl_hard_pct=self.config.execution.sl_hard_pct,
                            time_stop_hours=self.config.execution.time_stop_hours,
                            entry_time=candle_time,
                        )

                        current_trade = _OpenTrade(
                            entry_price=fill_price,
                            entry_time=candle_time,
                            notional=sizing.notional_usd,
                            quantity=sizing.quantity,
                            risk_usd=sizing.risk_usd,
                            score=intent.score,
                            exit_plan=exit_plan,
                        )

            # Track equity curve
            peak_equity = max(peak_equity, equity)
            dd_usd = peak_equity - equity
            dd_pct = dd_usd / peak_equity * 100 if peak_equity > 0 else 0
            max_dd_usd = max(max_dd_usd, dd_usd)
            max_dd_pct = max(max_dd_pct, dd_pct)

            # Sample equity curve (every 10 candles to avoid huge arrays)
            if i % 10 == 0 or i == len(df) - 1:
                equity_curve.append({
                    "date": str(df.index[i])[:19],
                    "equity": round(equity, 2),
                    "drawdown": round(dd_pct, 2),
                })

        # ── Force-close any open trade ─────────────────────────────
        if current_trade is not None:
            last_price = float(df.iloc[-1]["close"])
            exit_price = self._apply_slippage(last_price, "sell")
            fee = current_trade.notional * (self.fee_bps / 10000)
            pnl = (exit_price - current_trade.entry_price) * current_trade.quantity - fee
            pnl_pct = pnl / current_trade.notional if current_trade.notional > 0 else 0
            hold_mins = int((df.index[-1] - current_trade.entry_time).total_seconds() / 60)

            trades.append(Trade(
                symbol=symbol,
                entry_price=current_trade.entry_price,
                entry_time=current_trade.entry_time,
                exit_price=exit_price,
                exit_time=df.index[-1],
                exit_trigger="end_of_data",
                notional=current_trade.notional,
                quantity=current_trade.quantity,
                pnl=pnl,
                pnl_pct=pnl_pct,
                score=current_trade.score,
                r_multiple=0,
                risk_usd=current_trade.risk_usd,
                sl_price=current_trade.exit_plan.sl_price,
                tp_price=current_trade.exit_plan.tp_price,
                duration_minutes=hold_mins,
            ))
            equity += pnl

        # ── Compute metrics ────────────────────────────────────────
        return self._compute_results(
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            trades=trades,
            equity_curve=equity_curve,
            max_dd_usd=max_dd_usd,
            max_dd_pct=max_dd_pct,
            capitulations=capitulations,
            intents_emitted=intents_emitted,
            intents_blocked=intents_blocked,
        )

    def _apply_slippage(self, price: float, side: str) -> float:
        """Apply pessimistic slippage."""
        slip = price * (self.slippage_bps / 10000)
        return price + slip if side == "buy" else price - slip

    def _compute_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute minimal indicators for bounce catcher."""
        closes = df["close"].astype(float)

        # RSI
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        return {
            "rsi_15m": float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0,
            "funding_8h": 0.0001,  # neutral assumption
            "fear_greed": 25,       # moderate fear assumption
        }

    def _compute_results(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        trades: List[Trade],
        equity_curve: List[Dict],
        max_dd_usd: float,
        max_dd_pct: float,
        capitulations: int,
        intents_emitted: int,
        intents_blocked: int,
    ) -> BacktestResults:
        """Compute comprehensive performance metrics."""
        total_trades = len(trades)

        if total_trades == 0:
            return BacktestResults(
                symbol=symbol,
                timeframe=timeframe,
                period_start=str(df.index[0])[:10],
                period_end=str(df.index[-1])[:10],
                total_candles=len(df),
                equity_curve=equity_curve,
                capitulations_detected=capitulations,
                intents_emitted=intents_emitted,
                intents_blocked=intents_blocked,
            )

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        scratches = [t for t in trades if t.pnl == 0]

        total_pnl = sum(t.pnl for t in trades)
        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0.001

        # P&L per trade series for Sharpe
        pnl_series = [t.pnl for t in trades]
        pnl_arr = np.array(pnl_series)
        sharpe = 0.0
        if len(pnl_arr) > 1 and np.std(pnl_arr) > 0:
            # Annualized Sharpe (assume ~2 trades/day for crypto)
            sharpe = (np.mean(pnl_arr) / np.std(pnl_arr)) * math.sqrt(252 * 2)

        # Exit breakdown
        exits_by_trigger: Dict[str, int] = {}
        for t in trades:
            exits_by_trigger[t.exit_trigger] = exits_by_trigger.get(t.exit_trigger, 0) + 1

        return BacktestResults(
            symbol=symbol,
            timeframe=timeframe,
            period_start=str(df.index[0])[:10],
            period_end=str(df.index[-1])[:10],
            total_candles=len(df),
            trades=trades,
            total_trades=total_trades,
            wins=len(wins),
            losses=len(losses),
            scratches=len(scratches),
            total_pnl=total_pnl,
            avg_pnl_per_trade=total_pnl / total_trades,
            avg_win=gross_profit / len(wins) if wins else 0,
            avg_loss=-gross_loss / len(losses) if losses else 0,
            largest_win=max((t.pnl for t in trades), default=0),
            largest_loss=min((t.pnl for t in trades), default=0),
            profit_factor=gross_profit / gross_loss if gross_loss > 0 else float("inf"),
            win_rate=len(wins) / total_trades * 100,
            expectancy=total_pnl / total_trades,
            avg_r_multiple=np.mean([t.r_multiple for t in trades]) if trades else 0,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_usd=max_dd_usd,
            sharpe_ratio=sharpe,
            avg_hold_minutes=np.mean([t.duration_minutes for t in trades]),
            max_hold_minutes=max(t.duration_minutes for t in trades),
            equity_curve=equity_curve,
            exits_by_trigger=exits_by_trigger,
            capitulations_detected=capitulations,
            intents_emitted=intents_emitted,
            intents_blocked=intents_blocked,
        )


@dataclass
class _OpenTrade:
    """Internal: tracks an open position during backtest."""
    entry_price: float
    entry_time: datetime
    notional: float
    quantity: float
    risk_usd: float
    score: int
    exit_plan: ExitPlan
