"""Entry point: python -m services.crypto_trader

Starts the async crypto trader service with full boot reconciliation,
state restoration, and context-aware startup summary.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

# Allow running from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Load .env — root .env, root .env.secrets, then package .env (last wins)
from dotenv import load_dotenv
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_root, ".env"))
load_dotenv(os.path.join(_root, ".env.secrets"), override=True)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

from integrations.robinhood_crypto_client import RobinhoodCryptoClient, RobinhoodCryptoConfig
from services.crypto_trader.config import CryptoTraderConfig
from services.crypto_trader.supabase_repository import SupabaseCryptoRepository
from services.crypto_trader.trader import CryptoTraderService
from services.crypto_trader.boot import run_boot_reconciliation


def _fmt_age(iso_str: str | None) -> str:
    """Format an ISO timestamp as a human-readable age string."""
    if not iso_str:
        return "never"
    try:
        ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (now - ts).total_seconds()
        if delta < 60:
            return f"{int(delta)}s ago"
        if delta < 3600:
            return f"{int(delta / 60)}m ago"
        if delta < 86400:
            return f"{delta / 3600:.1f}h ago"
        return f"{delta / 86400:.1f}d ago"
    except Exception:
        return str(iso_str)[:19]


def _print_boot_context(repo: SupabaseCryptoRepository, config: CryptoTraderConfig) -> dict:
    """Load and print everything the bot needs to know on startup.

    Returns the previous agent_state dict (or empty dict) for state restoration.
    """
    mode = config.mode
    print("")
    print("=" * 64)
    print(f"  ZOE CRYPTO TRADER - BOOT CONTEXT (mode={mode})")
    print("=" * 64)

    # ── 1. Previous Agent State ──
    prev_state = repo.load_agent_state(mode, "default") or {}
    if prev_state:
        last_sync = prev_state.get("last_sync_ts")
        was_paused = prev_state.get("paused", False)
        was_degraded = prev_state.get("degraded", False)
        boot_run = prev_state.get("boot_run_id", "?")
        print(f"\n  [PREV STATE] Last sync: {_fmt_age(last_sync)}")
        print(f"    Paused: {was_paused} | Degraded: {was_degraded} | Boot: {boot_run}")
    else:
        print("\n  [PREV STATE] No previous agent state found (fresh start)")

    # ── 2. Account Snapshot ──
    cash_snap = repo.latest_cash_snapshot(mode) or {}
    holdings_snap = repo.latest_holdings_snapshot(mode) or {}
    cash = float(cash_snap.get("cash_available", 0))
    buying_power = float(cash_snap.get("buying_power", 0))
    holdings = holdings_snap.get("holdings", {})
    active_holdings = {k: float(v) for k, v in holdings.items() if float(v) > 0} if isinstance(holdings, dict) else {}

    print(f"\n  [ACCOUNT]")
    print(f"    Cash: ${cash:.2f} | Buying Power: ${buying_power:.2f}")
    if active_holdings:
        print(f"    Positions ({len(active_holdings)}):")
        for sym, qty in sorted(active_holdings.items()):
            print(f"      {sym}: {qty:.8g}")
    else:
        print("    Positions: none")

    # ── 3. Open Orders ──
    open_orders = repo.list_open_orders(mode)
    if open_orders:
        print(f"\n  [OPEN ORDERS] ({len(open_orders)})")
        for o in open_orders:
            sym = o.get("symbol", "?")
            side = o.get("side", "?")
            notional = o.get("notional", o.get("qty", "?"))
            status = o.get("status", "?")
            print(f"    {side.upper()} {sym} ${notional} [{status}]")
    else:
        print(f"\n  [OPEN ORDERS] none")

    # ── 4. Daily Notional ──
    from datetime import date
    daily_used = repo.get_daily_notional(date.today(), mode)
    print(f"\n  [DAILY LIMITS]")
    print(f"    Notional used: ${daily_used:.2f} / ${config.max_daily_notional:.2f}")
    print(f"    Max per trade: ${config.max_notional_per_trade:.2f}")
    print(f"    Max positions: {config.max_open_positions}")

    # ── 5. Recent Trades (fills) ──
    recent_fills = repo.recent_fills(mode, limit=5)
    if recent_fills:
        print(f"\n  [RECENT FILLS] (last {len(recent_fills)})")
        for f in recent_fills:
            sym = f.get("symbol", "?")
            side = f.get("side", "?")
            qty = float(f.get("qty", 0))
            price = float(f.get("price", 0))
            executed = f.get("executed_at", f.get("created_at", ""))
            print(f"    {side.upper()} {sym}: {qty:.8g} @ ${price:.2f} ({_fmt_age(executed)})")
    else:
        print(f"\n  [RECENT FILLS] none")

    # ── 6. Recent Orders ──
    recent_orders = repo.recent_orders(mode, limit=5)
    if recent_orders:
        print(f"\n  [RECENT ORDERS] (last {len(recent_orders)})")
        for o in recent_orders:
            sym = o.get("symbol", "?")
            side = o.get("side", "?")
            notional = o.get("notional")
            qty = o.get("qty")
            amount_str = f"${notional:.2f}" if notional else (f"qty={qty}" if qty else "?")
            status = o.get("status", "?")
            requested = o.get("created_at", "")
            print(f"    {side.upper()} {sym} {amount_str} [{status}] ({_fmt_age(requested)})")
    else:
        print(f"\n  [RECENT ORDERS] none")

    # ── 7. Last Scan Results ──
    last_scans = repo.latest_candidate_scans(mode)
    if last_scans:
        scan_ts = last_scans[0].get("created_at", "")
        print(f"\n  [LAST SCAN] ({_fmt_age(scan_ts)}) -- {len(last_scans)} symbols")
        for s in last_scans[:5]:
            sym = s.get("symbol", "?")
            score = s.get("score", 0)
            strategy = s.get("recommended_strategy", "?")
            info = s.get("info", {})
            rsi = info.get("rsi")
            rsi_str = f"RSI {rsi:.0f}" if rsi is not None else "RSI --"
            print(f"    {sym}: score={score:.1f} strategy={strategy} {rsi_str}")
        if len(last_scans) > 5:
            print(f"    ... +{len(last_scans) - 5} more")
    else:
        print(f"\n  [LAST SCAN] no previous scan data")

    # ── 8. Recent Signals/Thoughts ──
    recent_signals = repo.recent_thoughts(mode, limit=5, thought_type="signal")
    recent_paper = repo.recent_thoughts(mode, limit=3, thought_type="paper_trade")
    if recent_signals:
        print(f"\n  [RECENT SIGNALS] (last {len(recent_signals)})")
        for t in recent_signals:
            content = t.get("content", "")[:80]
            created = t.get("created_at", "")
            print(f"    {_fmt_age(created)}: {content}")

    if recent_paper:
        print(f"\n  [RECENT PAPER TRADES] (last {len(recent_paper)})")
        for t in recent_paper:
            content = t.get("content", "")[:80]
            created = t.get("created_at", "")
            print(f"    {_fmt_age(created)}: {content}")

    if not recent_signals and not recent_paper:
        print(f"\n  [RECENT SIGNALS] none")

    # ── 9. Realized P&L ──
    pnl = repo.get_realized_pnl(mode)
    print(f"\n  [P&L] Realized: ${pnl:.2f}")

    print("")
    print("=" * 64)
    print("")

    return prev_state


async def _warm_price_cache(service: CryptoTraderService) -> None:
    """Do an initial price fetch to seed the cache before the main loop starts.

    This way the first scan (at t=0) already has at least 1 tick per symbol,
    and we're not waiting a full 60s for the first data point.
    """
    from services.crypto_trader.scanner import WATCHLIST
    try:
        batch = await service.client.get_best_bid_ask_batch(WATCHLIST)
        count = 0
        for result in batch.get("results", []):
            symbol = result.get("symbol", "")
            bid = float(result.get("bid_inclusive_of_sell_spread", result.get("bid_price", 0)))
            ask = float(result.get("ask_inclusive_of_buy_spread", result.get("ask_price", 0)))
            if bid > 0 and ask > 0:
                service.price_cache.record(symbol, bid, ask)
                count += 1
        print(f"[ZOE] Price cache warmed: {count}/{len(WATCHLIST)} symbols seeded")
    except Exception as e:
        print(f"[ZOE] Price cache warm-up failed (non-fatal): {e}")


async def main() -> None:
    print("[ZOE] Initializing crypto trader service...")

    # Robinhood client
    rh_config = RobinhoodCryptoConfig.from_env()
    if not rh_config.api_key or not rh_config.private_key_seed:
        print("[ZOE] ERROR: Set RH_CRYPTO_API_KEY and RH_CRYPTO_PRIVATE_KEY_SEED env vars")
        sys.exit(1)

    rh_client = RobinhoodCryptoClient(rh_config)

    # Supabase repository
    repo = SupabaseCryptoRepository()

    # Trader config
    trader_config = CryptoTraderConfig()

    # ── Print rich boot context ──
    prev_state = _print_boot_context(repo, trader_config)

    # Create service
    service = CryptoTraderService(client=rh_client, repository=repo, config=trader_config)

    # ── Restore previous state flags ──
    if prev_state:
        if prev_state.get("paused"):
            service._paused = True
            print("[ZOE] Restored paused state from previous session")
        if prev_state.get("degraded"):
            service._degraded = True
            print("[ZOE] Restored degraded state from previous session")

    print(f"[ZOE] Mode: {trader_config.mode}")
    print(f"[ZOE] Live trading: {trader_config.live_ready()}")
    print(f"[ZOE] Reconcile interval: {trader_config.reconcile_interval_seconds}s")
    print(f"[ZOE] Order poll interval: {trader_config.order_poll_interval_seconds}s")

    # ── Boot reconciliation — runs BEFORE the main loop ──
    boot_result = await run_boot_reconciliation(rh_client, repo, trader_config)

    if boot_result.action == "halt":
        print(f"[ZOE] HALTED: {boot_result.reason}")
        service._paused = True
    elif boot_result.action == "safe_mode":
        print(f"[ZOE] SAFE MODE: {boot_result.reason} ({boot_result.safe_mode_seconds}s)")
        service._safe_mode_until = time.time() + boot_result.safe_mode_seconds
    else:
        print("[ZOE] Boot reconciliation: NORMAL -- ready to trade")
        # Clear any stale degraded/paused from previous state if boot is clean
        if prev_state.get("degraded") and not service._degraded:
            service._degraded = False
            print("[ZOE] Cleared stale degraded flag (boot checks passed)")

    # ── Warm the price cache before starting the main loop ──
    await _warm_price_cache(service)

    # ── Load historical candle data from CoinGecko ──
    try:
        historical_count = await service.candle_manager.load_historical()
        print(f"[ZOE] Historical candles loaded: {historical_count}")
    except Exception as e:
        print(f"[ZOE] Historical candle load failed (non-fatal): {e}")
        historical_count = 0

    # ── Write boot thought ──
    service._write_thought(
        f"Service booted (mode={trader_config.mode}, run_id={boot_result.run_id}). "
        f"Boot: {boot_result.action} in {boot_result.duration_ms}ms. "
        f"Paused={service._paused}, Degraded={service._degraded}. "
        f"Price cache seeded with {len(service.price_cache.symbols)} symbols. "
        f"Historical candles: {historical_count}.",
        thought_type="health",
    )

    try:
        await service.run_forever()
    except KeyboardInterrupt:
        print("\n[ZOE] Shutting down...")
    finally:
        # Save final state before exit
        service._save_agent_state_snapshot()
        print("[ZOE] Agent state saved.")
        await rh_client.close()
        print("[ZOE] Closed.")


if __name__ == "__main__":
    asyncio.run(main())
