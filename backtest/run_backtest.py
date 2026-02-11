"""
Run Backtest — CLI entry point for bounce catcher backtesting.

Usage examples:

  # Smoke test with synthetic data (5 injected capitulations)
  python backtest/run_backtest.py --synthetic

  # Backtest with a CSV file
  python backtest/run_backtest.py --csv data/btc_15m.csv

  # Backtest with live Polygon data (last 90 days)
  python backtest/run_backtest.py --polygon --symbol BTC-USD --days 90

  # Custom equity and config
  python backtest/run_backtest.py --synthetic --equity 5000 --candles 5000
"""

import argparse
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.engine import BacktestEngine
from backtest.data_loader import (
    load_csv_candles,
    fetch_polygon_candles,
    generate_synthetic_candles,
)


def main():
    parser = argparse.ArgumentParser(description="Bounce Catcher Backtester")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--synthetic", action="store_true", help="Use synthetic data with injected capitulations")
    group.add_argument("--csv", type=str, help="Path to CSV file with OHLCV data")
    group.add_argument("--polygon", action="store_true", help="Fetch from Polygon.io")

    parser.add_argument("--symbol", default="BTC-USD", help="Trading symbol (default: BTC-USD)")
    parser.add_argument("--timeframe", default="15m", help="Candle timeframe (default: 15m)")
    parser.add_argument("--equity", type=float, default=2000.0, help="Starting equity (default: $2000)")
    parser.add_argument("--days", type=int, default=90, help="Days of history for Polygon (default: 90)")
    parser.add_argument("--candles", type=int, default=3000, help="Number of synthetic candles (default: 3000)")
    parser.add_argument("--capitulations", type=int, default=8, help="Injected capitulations for synthetic (default: 8)")
    parser.add_argument("--slippage", type=float, default=10.0, help="Slippage in bps (default: 10)")
    parser.add_argument("--fee", type=float, default=5.0, help="Fee per side in bps (default: 5)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for synthetic data (default: 42)")

    args = parser.parse_args()

    # Load data
    if args.synthetic:
        print(f"\nGenerating {args.candles} synthetic candles ({args.capitulations} capitulations, seed={args.seed})...")
        df = generate_synthetic_candles(
            n=args.candles,
            include_capitulations=args.capitulations,
            seed=args.seed,
        )
    elif args.csv:
        print(f"\nLoading candles from {args.csv}...")
        df = load_csv_candles(args.csv, symbol=args.symbol)
    elif args.polygon:
        print(f"\nFetching {args.days} days of {args.symbol}/{args.timeframe} from Polygon...")
        df = fetch_polygon_candles(args.symbol, args.timeframe, args.days)

    print(f"Data loaded: {len(df)} candles ({df.index[0]} to {df.index[-1]})")

    # Run backtest
    engine = BacktestEngine(
        starting_equity=args.equity,
        slippage_bps=args.slippage,
        fee_bps=args.fee,
    )
    results = engine.run(df, symbol=args.symbol, timeframe=args.timeframe)
    results.print_summary()

    # Print individual trades
    if results.trades:
        print("\n  Individual Trades:")
        print(f"  {'#':>3}  {'Entry':>12}  {'Exit':>12}  {'P&L':>10}  {'R':>6}  {'Score':>5}  {'Trigger':>10}  {'Hold':>8}")
        print(f"  {'---':>3}  {'---':>12}  {'---':>12}  {'---':>10}  {'---':>6}  {'---':>5}  {'---':>10}  {'---':>8}")
        for i, t in enumerate(results.trades, 1):
            pnl_str = f"{'+'if t.pnl >= 0 else ''}{t.pnl:.2f}"
            hold_str = f"{t.duration_minutes}m"
            print(f"  {i:>3}  ${t.entry_price:>10,.2f}  ${t.exit_price:>10,.2f}  {pnl_str:>10}  {t.r_multiple:>5.1f}R  {t.score:>5}  {t.exit_trigger:>10}  {hold_str:>8}")

    print(f"\n  Final Equity: ${args.equity + results.total_pnl:,.2f} (started at ${args.equity:,.2f})")
    return results


if __name__ == "__main__":
    main()
