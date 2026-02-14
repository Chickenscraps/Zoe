"""Entry point: python -m services.crypto_trader

Starts the async crypto trader service with full boot reconciliation,
state restoration, and context-aware startup summary.

Supports broker backends: paper, robinhood, kraken (via BROKER_TYPE env).
Supports market data sources: polling, kraken_ws (via MARKET_DATA_SOURCE env).
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

from services.crypto_trader.config import CryptoTraderConfig
from services.crypto_trader.supabase_repository import SupabaseCryptoRepository
from services.crypto_trader.trader import CryptoTraderService
from services.crypto_trader.boot import run_boot_reconciliation
from services.crypto_trader.broker_factory import create_broker


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
    """Load and print everything the bot needs to know on startup."""
    mode = config.mode
    print("")
    print("=" * 64)
    print(f"  ZOE CRYPTO TRADER - BOOT CONTEXT (mode={mode}, broker={config.broker_type})")
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


async def _warm_price_cache_rh(service: CryptoTraderService, rh_client) -> None:
    """Warm price cache via Robinhood batch API (legacy path)."""
    from services.crypto_trader.scanner import WATCHLIST
    try:
        batch = await rh_client.get_best_bid_ask_batch(WATCHLIST)
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


async def _warm_price_cache_kraken(service: CryptoTraderService, rest_client) -> None:
    """Warm price cache via Kraken REST ticker (Kraken path)."""
    from services.crypto_trader.symbol_map import to_internal
    try:
        tickers = await rest_client.get_ticker(["XBTUSD", "ETHUSD", "SOLUSD", "DOGEUSD", "ADAUSD", "XRPUSD", "LTCUSD"])
        count = 0
        for key, t in tickers.items():
            bid = float(t.bid)
            ask = float(t.ask)
            if bid > 0 and ask > 0:
                internal_sym = to_internal(key) if "/" in key else key
                service.price_cache.record(internal_sym, bid, ask)
                count += 1
        print(f"[ZOE] Price cache warmed (Kraken REST): {count} symbols seeded")
    except Exception as e:
        print(f"[ZOE] Price cache warm-up failed (non-fatal): {e}")


def _build_kraken_components(config: CryptoTraderConfig, repo: SupabaseCryptoRepository, broker):
    """Build Kraken-specific components (market data, WS, order executor, etc.)."""
    components = {}

    # REST client for market data (may differ from broker's client)
    from services.crypto_trader.kraken_client import KrakenRestClient
    rest_client = KrakenRestClient(
        api_key=config.kraken_api_key,
        api_secret=config.kraken_api_secret,
        base_url=config.kraken_base_url or None,
    )
    components["rest_client"] = rest_client

    if config.market_data_source == "kraken_ws":
        # WS Manager (public)
        from services.crypto_trader.kraken_ws_manager import KrakenWsManager
        ws_manager = KrakenWsManager(url=config.kraken_ws_url)
        components["ws_manager"] = ws_manager

        # MarketDataService
        from services.crypto_trader.market_data_service import MarketDataService
        market_data = MarketDataService(
            rest_client=rest_client,
            ws_manager=ws_manager,
            repository=repo,
        )
        components["market_data_service"] = market_data

    if config.kraken_api_key and config.kraken_api_secret:
        # WS Private (authenticated) — for fill tracking
        from services.crypto_trader.kraken_ws_private import KrakenWsPrivate
        ws_private = KrakenWsPrivate(
            rest_client=rest_client,
            ws_auth_url=config.kraken_ws_auth_url,
        )
        components["ws_private"] = ws_private

    # Order executor
    from services.crypto_trader.order_executor import OrderExecutor
    order_executor = OrderExecutor(broker=broker, repository=repo, mode=config.mode)
    components["order_executor"] = order_executor

    # Fill processor
    from services.crypto_trader.fill_processor import FillProcessor
    fill_processor = FillProcessor(repository=repo, mode=config.mode)
    components["fill_processor"] = fill_processor

    # PnL service
    from services.crypto_trader.pnl_service import PnlService
    pnl_service = PnlService(repository=repo, mode=config.mode)
    components["pnl_service"] = pnl_service

    # Repositioner
    from services.crypto_trader.repositioner import Repositioner
    repositioner = Repositioner(
        broker=broker,
        repository=repo,
        mode=config.mode,
        timeout_s=config.repositioner_timeout_s,
    )
    components["repositioner"] = repositioner

    # Circuit breaker
    from services.crypto_trader.circuit_breaker import CircuitBreaker
    circuit_breaker = CircuitBreaker(threshold_s=config.stale_data_threshold_s)
    components["circuit_breaker"] = circuit_breaker

    return components


async def main() -> None:
    print("[ZOE] Initializing crypto trader service...")

    # Trader config (reads BROKER_TYPE, MARKET_DATA_SOURCE, etc.)
    trader_config = CryptoTraderConfig()
    print(f"[ZOE] Broker type: {trader_config.broker_type}")
    print(f"[ZOE] Market data source: {trader_config.market_data_source}")

    # Supabase repository
    repo = SupabaseCryptoRepository()

    # ── Create broker via factory ──
    rh_client = None
    if trader_config.broker_type == "robinhood":
        # Legacy path: also need raw client for polling
        from integrations.robinhood_crypto_client import RobinhoodCryptoClient, RobinhoodCryptoConfig
        rh_config = RobinhoodCryptoConfig.from_env()
        if not rh_config.api_key or not rh_config.private_key_seed:
            print("[ZOE] ERROR: Set RH_CRYPTO_API_KEY and RH_CRYPTO_PRIVATE_KEY_SEED env vars")
            sys.exit(1)
        rh_client = RobinhoodCryptoClient(rh_config)

    broker = await create_broker(trader_config, repo=repo, market_data_provider=None)

    # For paper broker, we need a market data provider — use a simple wrapper
    if trader_config.broker_type == "paper":
        # PaperBroker is created inside create_broker; it needs a market_data_provider
        # The factory already handles this, but for price-cache-only paper mode,
        # we pass the price_cache later via service. Re-create with proper provider.
        from services.crypto_trader.broker import PaperBroker

        class _PriceCacheProvider:
            """Minimal provider that exposes get_current_price for PaperBroker."""
            def __init__(self):
                self.price_cache = None

            async def get_current_price(self, symbol: str) -> float:
                if self.price_cache:
                    snap = self.price_cache.snapshot(symbol)
                    return snap.get("mid", 0)
                return 0.0

        mdp = _PriceCacheProvider()
        broker = PaperBroker(mdp, repo, starting_cash=trader_config.starting_equity)

    # ── Build Kraken components if needed ──
    kraken_components: dict = {}
    if trader_config.broker_type == "kraken" or trader_config.market_data_source == "kraken_ws":
        print("[ZOE] Building Kraken components...")
        kraken_components = _build_kraken_components(trader_config, repo, broker)

    # ── Print rich boot context ──
    prev_state = _print_boot_context(repo, trader_config)

    # ── Create service ──
    service = CryptoTraderService(
        broker=broker,
        repository=repo,
        config=trader_config,
        market_data_service=kraken_components.get("market_data_service"),
        order_executor=kraken_components.get("order_executor"),
        fill_processor=kraken_components.get("fill_processor"),
        pnl_service=kraken_components.get("pnl_service"),
        repositioner=kraken_components.get("repositioner"),
        circuit_breaker=kraken_components.get("circuit_breaker"),
        ws_private=kraken_components.get("ws_private"),
        ws_manager=kraken_components.get("ws_manager"),
        rh_client=rh_client,
    )

    # Wire PaperBroker's market data provider to service's price cache
    if trader_config.broker_type == "paper" and hasattr(broker, "mdp") and hasattr(broker.mdp, "price_cache"):
        broker.mdp.price_cache = service.price_cache

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
    if rh_client:
        boot_result = await run_boot_reconciliation(rh_client, repo, trader_config)
    else:
        # For Kraken/paper, use broker-based boot
        boot_result = await run_boot_reconciliation(broker, repo, trader_config)

    if boot_result.action == "halt":
        print(f"[ZOE] HALTED: {boot_result.reason}")
        service._paused = True
    elif boot_result.action == "safe_mode":
        print(f"[ZOE] SAFE MODE: {boot_result.reason} ({boot_result.safe_mode_seconds}s)")
        service._safe_mode_until = time.time() + boot_result.safe_mode_seconds
    else:
        print("[ZOE] Boot reconciliation: NORMAL -- ready to trade")
        if prev_state.get("degraded") and not service._degraded:
            service._degraded = False
            print("[ZOE] Cleared stale degraded flag (boot checks passed)")

    # ── Warm the price cache before starting the main loop ──
    if rh_client and trader_config.market_data_source == "polling":
        await _warm_price_cache_rh(service, rh_client)
    elif "rest_client" in kraken_components:
        await _warm_price_cache_kraken(service, kraken_components["rest_client"])

    # ── Load historical candle data from CoinGecko ──
    try:
        historical_count = await service.candle_manager.load_historical()
        print(f"[ZOE] Historical candles loaded: {historical_count}")
    except Exception as e:
        print(f"[ZOE] Historical candle load failed (non-fatal): {e}")
        historical_count = 0

    # ── Write boot thought ──
    service._write_thought(
        f"Service booted (mode={trader_config.mode}, broker={trader_config.broker_type}, "
        f"data={trader_config.market_data_source}, run_id={boot_result.run_id}). "
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
        # Close clients
        if rh_client:
            await rh_client.close()
        if "rest_client" in kraken_components:
            await kraken_components["rest_client"].close()
        print("[ZOE] Closed.")


if __name__ == "__main__":
    asyncio.run(main())
