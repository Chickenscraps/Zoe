"""
Crypto Trader Orchestrator — unified entry point for the trading pipeline.

Usage:
    python -m services.crypto_trader --mode paper   # safe default
    python -m services.crypto_trader --mode live     # requires LIVE_TRADING_CONFIRMED=true

Startup sequence:
1. Load config from env (defaults to mode="paper" for safety)
2. Init Kraken REST + WS clients
3. Init LocalEventStore (SQLite WAL)
4. Run startup hydration (balance, holdings, reconciliation)
5. Hydrate FIFO from local_store.get_all_fills(mode)
6. Connect public WS -> PriceCache ticker callback
7. Connect private WS -> FillStreamService execution callback
8. Start fill stream, order management loop, flush worker
9. Graceful shutdown on SIGINT/SIGTERM
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

# ── Load .env from project root ───────────────────────────
from dotenv import load_dotenv

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_root, ".env"))
load_dotenv(os.path.join(_root, ".env.secrets"))

# ── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("crypto_trader")

# Reduce noise from libraries
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZOE Crypto Trader")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default=os.getenv("TRADING_MODE", "paper"),
        help="Trading mode (default: paper)",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite DB path (default: data/crypto_trader_{mode}.db)",
    )
    parser.add_argument(
        "--tick-interval",
        type=float,
        default=float(os.getenv("TICK_INTERVAL", "5.0")),
        help="Order management tick interval in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--pairs",
        nargs="+",
        default=os.getenv("TRADING_PAIRS", "BTC/USD").split(","),
        help="Trading pairs for WS ticker subscription (default: BTC/USD)",
    )
    # ── Scanner config knobs (profitability-focused defaults) ──
    parser.add_argument(
        "--scan-interval",
        type=float,
        default=float(os.getenv("SCAN_INTERVAL", "120.0")),
        help="Seconds between trade scanner sweeps (default: 120)",
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=int(os.getenv("MAX_OPEN_POSITIONS", "3")),
        help="Max concurrent open positions (default: 3)",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=int(os.getenv("MIN_TRADE_SCORE", "65")),
        help="Minimum scanner score to consider a trade (default: 65)",
    )
    parser.add_argument(
        "--max-notional",
        type=float,
        default=float(os.getenv("MAX_TRADE_NOTIONAL", "50.0")),
        help="Max USD notional per trade (default: 50)",
    )
    parser.add_argument(
        "--max-exposure",
        type=float,
        default=float(os.getenv("MAX_TOTAL_EXPOSURE", "150.0")),
        help="Max total USD exposure across all positions (default: 150)",
    )
    parser.add_argument(
        "--min-volume-24h",
        type=float,
        default=float(os.getenv("MIN_VOLUME_24H", "50000")),
        help="Min 24h volume in USD to consider a coin (default: 50000)",
    )
    parser.add_argument(
        "--max-spread-pct",
        type=float,
        default=float(os.getenv("MAX_SPREAD_PCT", "0.30")),
        help="Max spread %% to trade (default: 0.30)",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=float(os.getenv("COOLDOWN_SECONDS", "600")),
        help="Per-symbol cooldown between trades in seconds (default: 600)",
    )
    parser.add_argument(
        "--disable-scanner",
        action="store_true",
        default=os.getenv("DISABLE_SCANNER", "").lower() == "true",
        help="Disable the multi-coin trade scanner",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.getenv("DRY_RUN", "").lower() == "true",
        help="Dry run mode: score and log trades without executing",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    mode = args.mode

    # ── Safety gate: live mode requires explicit confirmation ──
    if mode == "live":
        confirmed = os.getenv("LIVE_TRADING_CONFIRMED", "").lower()
        if confirmed != "true":
            logger.critical(
                "LIVE trading requires LIVE_TRADING_CONFIRMED=true environment variable. "
                "This is a safety gate to prevent accidental live trading. Exiting."
            )
            sys.exit(1)
        logger.warning("=" * 60)
        logger.warning("  LIVE TRADING MODE — REAL MONEY AT RISK")
        logger.warning("=" * 60)
    else:
        logger.info("Paper trading mode (no real orders)")

    # ── Resolve DB path ──
    db_path = args.db_path or f"data/crypto_trader_{mode}.db"

    logger.info("Starting ZOE Crypto Trader (mode=%s, db=%s)", mode, db_path)

    # ── 1. Initialize Kraken clients ──
    from integrations.kraken_client.config import KrakenConfig
    from integrations.kraken_client.client import KrakenClient
    from integrations.kraken_client.ws import KrakenWebSocket

    config = KrakenConfig.from_env()
    exchange = KrakenClient(config)
    ws = KrakenWebSocket(config)

    # ── 2. Initialize Supabase client ──
    from supabase import create_client

    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
    if not sb_url or not sb_key:
        logger.warning("Supabase not configured — running without remote persistence")
        sb_client = None
    else:
        sb_client = create_client(sb_url, sb_key)
        logger.info("Supabase client initialized")

    # ── 3. Initialize LocalEventStore ──
    from services.local_store import LocalEventStore

    store = LocalEventStore(db_path)
    logger.info("Local store initialized: %s", db_path)

    # ── 4. Run startup hydration ──
    from services.reconciliation.hydration import StartupHydrator, HydrationResult

    hydrator = StartupHydrator(
        supabase_client=sb_client,
        exchange_client=exchange,
        mode=mode,
    )

    try:
        hydration = await hydrator.hydrate()
    except Exception as e:
        logger.critical("Hydration failed fatally: %s", e, exc_info=True)
        await exchange.close()
        sys.exit(1)

    if not hydration.ready:
        logger.critical(
            "Hydration gates FAILED — system is NOT ready to trade. "
            "Errors: %s",
            "; ".join(hydration.errors),
        )
        await exchange.close()
        sys.exit(1)

    logger.info(
        "Hydration OK: cash=$%.2f, %d positions, recon=%s",
        hydration.cash_balance,
        len(hydration.holdings),
        hydration.reconciliation_status,
    )

    # ── 5. Hydrate FIFO from local fills ──
    from services.accounting.fifo_matcher import FIFOMatcher

    stored_fills = store.get_all_fills(mode)
    if stored_fills:
        fifo = FIFOMatcher.from_fills(stored_fills)
        logger.info(
            "FIFO hydrated from %d fills (realized P&L: $%.2f, %d open symbols)",
            len(stored_fills),
            fifo.get_realized_pnl(),
            len(fifo.get_all_symbols()),
        )
    else:
        fifo = FIFOMatcher()
        logger.info("FIFO started fresh (no prior fills)")

    # ── 6. Initialize PriceCache ──
    from services.crypto_trader.price_cache import PriceCache

    price_cache = PriceCache(store)

    # WS ticker callback: parse Kraken WS v2 ticker message → update cache
    def _on_ticker_msg(data: dict[str, Any]) -> None:
        """Parse Kraken WS v2 ticker and feed PriceCache.

        Kraken WS v2 ticker format:
        {
            "channel": "ticker",
            "type": "snapshot" | "update",
            "data": [{
                "symbol": "BTC/USD",
                "bid": 69000.0, "bid_qty": 1.5,
                "ask": 69010.0, "ask_qty": 2.0,
                "last": 69005.0, "volume": 1234.5,
                ...
            }]
        }
        """
        from integrations.kraken_client.symbols import from_kraken

        for item in data.get("data", []):
            raw_symbol = item.get("symbol", "")
            bid = float(item.get("bid", 0))
            ask = float(item.get("ask", 0))
            if raw_symbol and bid > 0 and ask > 0:
                symbol = from_kraken(raw_symbol) if "/" in raw_symbol else raw_symbol
                price_cache.update(symbol, bid, ask)

    ws.on_ticker(_on_ticker_msg)

    # ── 7. Connect public WS and subscribe to tickers ──
    await ws.connect_public()

    # Build initial WS subscription list: CLI --pairs + focus pairs from DB
    ws_pairs = set(p.strip() for p in args.pairs if p.strip())

    # Load dynamic focus pairs from market_focus_config
    if sb_client and not args.disable_scanner:
        try:
            resp = sb_client.table("market_focus_config").select("symbol").execute()
            if resp.data:
                from integrations.kraken_client.symbols import to_kraken
                for row in resp.data:
                    sym = row.get("symbol", "")
                    if sym:
                        try:
                            ws_pairs.add(to_kraken(sym, for_ws=True))
                        except Exception:
                            ws_pairs.add(sym)  # fallback: use as-is
                logger.info("Loaded %d focus pairs from market_focus_config", len(resp.data))
        except Exception as e:
            logger.warning("Failed to load focus pairs: %s", e)

    ws_pairs_list = sorted(ws_pairs)
    if ws_pairs_list:
        # Kraken WS v2 can handle large symbol lists in a single subscribe
        await ws.subscribe_ticker(ws_pairs_list)
        logger.info("Subscribed to %d ticker pairs", len(ws_pairs_list))

    # ── 8. Connect private WS for executions ──
    try:
        ws_token = await exchange.get_ws_token()
        await ws.connect_private(ws_token)
        logger.info("Private WS connected (executions channel)")
    except Exception as e:
        logger.error("Private WS connection failed: %s", e)
        if mode == "live":
            logger.critical("Cannot start live trading without private WS. Exiting.")
            await _shutdown(ws, exchange)
            sys.exit(1)

    # ── 8b. Initialize HeartbeatMonitor ──
    from services.risk.heartbeat_monitor import HeartbeatMonitor

    async def _on_heartbeat_timeout(connection_name: str) -> None:
        """Dead-man's switch: cancel all orders if WS goes down."""
        logger.critical("HEARTBEAT TIMEOUT: %s — cancelling all open orders", connection_name)
        store.insert_event(
            mode=mode,
            source="heartbeat_monitor",
            type="RISK",
            subtype="WS_TIMEOUT",
            symbol="",
            body=f"WebSocket heartbeat lost: {connection_name}",
        )
        # Cancel all tracked orders
        for oid in list(order_mgr._orders.keys()):
            try:
                await order_mgr.cancel_order(oid, reason="ws_heartbeat_lost")
            except Exception as e:
                logger.error("Failed to cancel order %s on heartbeat timeout: %s", oid, e)

    async def _on_heartbeat_reconnect(connection_name: str) -> None:
        """Attempt WS reconnection."""
        logger.info("Heartbeat reconnecting: %s", connection_name)

    heartbeat_monitor = HeartbeatMonitor(
        timeout_seconds=10.0,
        max_missed_before_action=3,
        on_timeout=_on_heartbeat_timeout,
        on_reconnect=_on_heartbeat_reconnect,
    )
    heartbeat_monitor.register("public_ws")
    heartbeat_monitor.register("private_ws")
    await heartbeat_monitor.start()
    logger.info("Heartbeat monitor started")

    # Augment ticker callback to feed heartbeat
    _original_ticker_cb = _on_ticker_msg

    def _on_ticker_msg_with_heartbeat(data: dict[str, Any]) -> None:
        heartbeat_monitor.heartbeat("public_ws")
        _original_ticker_cb(data)

    ws.on_ticker(_on_ticker_msg_with_heartbeat)

    # ── 9. Initialize FillStreamService ──
    from services.accounting.fee_tracker import FeeTracker
    from services.crypto_trader.fill_stream import FillStreamService

    fee_tracker = FeeTracker(sb_client) if sb_client else FeeTracker(None)
    fill_stream = FillStreamService(
        ws=ws,
        exchange=exchange,
        fifo_matcher=fifo,
        local_store=store,
        supabase_client=sb_client,
        fee_tracker=fee_tracker,
        mode=mode,
    )
    await fill_stream.start()
    logger.info("Fill stream service started")

    # ── Entry intent tracking for fill routing ──
    # Maps intent_group_id → TradeIntent for matching fills to positions
    _entry_intents: dict[str, Any] = {}

    # ── 10. Initialize OrderManager ──
    from services.crypto_trader.order_manager import OrderManager

    order_mgr = OrderManager(
        broker=exchange,
        repo=store,
        mode=mode,
        on_event=lambda evt: store.insert_event(
            mode=mode,
            source="order_manager",
            type="ORDER",
            subtype=evt.get("event_type", "unknown").upper(),
            symbol=evt.get("symbol", ""),
            body=f"Order {evt.get('order_id', '?')}: {evt.get('from_status', '?')} → {evt.get('to_status', '?')}",
            meta=evt,
        ),
    )
    # Recover any in-flight orders from DB
    order_mgr.recover_from_db()
    logger.info("Order manager initialized (recovered %d in-flight orders)", len(order_mgr._orders))

    # ── 10b. Initialize CircuitBreaker ──
    from services.risk.circuit_breaker import CircuitBreaker

    starting_equity = hydration.cash_balance + sum(
        float(v) for v in hydration.holdings.values()
    )
    circuit_breaker = CircuitBreaker(
        starting_equity=starting_equity,
        on_trip=lambda evt: store.insert_event(
            mode=mode,
            source="circuit_breaker",
            type="RISK",
            subtype=f"TRIP_{evt.severity.upper()}",
            symbol="",
            body=evt.reason,
            meta=evt.details,
        ),
    )
    logger.info("Circuit breaker initialized (equity=$%.2f)", starting_equity)

    # ── 10b-ii. Initialize PositionTracker ──
    from services.crypto_trader.position_tracker import PositionTracker

    position_tracker = PositionTracker(local_store=store, mode=mode)
    recovered_positions = position_tracker.recover()
    if recovered_positions > 0:
        logger.info("Recovered %d open position(s) from DB", recovered_positions)
        # Feed recovered positions into circuit breaker
        for pos in position_tracker.get_open():
            circuit_breaker.update_position(pos.symbol, pos.notional)

    # ── 10c. Initialize IndicatorEngine + TradeScanner ──
    from services.position_sizer import PositionSizer

    position_sizer = PositionSizer.from_config()

    indicator_engine = None
    scanner = None
    if not args.disable_scanner and sb_client:
        from services.crypto_trader.indicators import IndicatorEngine
        from services.crypto_trader.trade_scanner import TradeScanner

        indicator_engine = IndicatorEngine()
        price_cache.set_indicator_engine(indicator_engine)
        logger.info("Indicator engine initialized (feeds from PriceCache WS ticks)")

        scanner = TradeScanner(
            supabase_client=sb_client,
            price_cache=price_cache,
            indicator_engine=indicator_engine,
            circuit_breaker=circuit_breaker,
            position_sizer=position_sizer,
            mode=mode,
            min_score=args.min_score,
            max_spread_pct=args.max_spread_pct,
            min_volume_24h=args.min_volume_24h,
            max_positions=args.max_positions,
            max_notional=args.max_notional,
            max_exposure=args.max_exposure,
            cooldown_seconds=args.cooldown_seconds,
            dry_run=args.dry_run,
        )
        logger.info(
            "Trade scanner initialized (min_score=%d, max_pos=%d, exposure=$%.0f, cooldown=%ds, dry_run=%s)",
            args.min_score, args.max_positions, args.max_exposure,
            int(args.cooldown_seconds), args.dry_run,
        )
    elif args.disable_scanner:
        logger.info("Trade scanner DISABLED by flag")
    else:
        logger.warning("Trade scanner disabled (no Supabase client)")

    # ── 10d. Initialize ExitManager ──
    from services.crypto_trader.exit_manager import ExitManager, ExitPolicy

    exit_policy = ExitPolicy.from_config()
    exit_manager = ExitManager(
        order_manager=order_mgr,
        price_cache=price_cache,
        indicator_engine=indicator_engine,
        policy=exit_policy,
        position_tracker=position_tracker,
        circuit_breaker=circuit_breaker,
        mode=mode,
    )
    # Recover exit management for any positions that survived restart
    if position_tracker.position_count() > 0:
        exit_manager.recover_from_tracker(position_tracker)
    logger.info(
        "Exit manager initialized (TP=%.1f%%, SL_ATR=%.1fx, hard=%.1f%%, time_stop=%.0fh)",
        exit_policy.tp_pct * 100, exit_policy.sl_atr_mult,
        exit_policy.sl_hard_pct * 100, exit_policy.time_stop_hours,
    )

    # ── 10e. Wire fill stream → ExitManager + PositionTracker ──
    # This callback routes fills to the position lifecycle:
    #   Entry fill → open position → start exit management (TP/SL)
    #   Exit fill → close position → record P&L
    async def _on_fill_routed(fill: dict[str, Any]) -> None:
        """Route fills to position tracker and exit manager."""
        order_id = fill.get("order_id", "")
        symbol = fill.get("symbol", "")
        side = fill.get("side", "")
        qty = float(fill.get("qty", 0))
        price = float(fill.get("price", 0))

        if not order_id or qty <= 0 or price <= 0:
            return

        # Check if this is an EXIT fill
        if exit_manager.is_exit_order(order_id):
            exit_manager.on_exit_fill(symbol, qty, price, order_id)
            logger.info(
                "Exit fill routed: %s %s %.6f @ $%.2f [order=%s]",
                side.upper(), symbol, qty, price, order_id[:8],
            )
            return

        # Check if this is an ENTRY fill (matches a tracked intent)
        matched_intent = None
        matched_intent_id = None
        for intent_id, intent in list(_entry_intents.items()):
            # Match by symbol — the order_mgr tracks order_id → intent_group_id
            # but we can match by checking if the order belongs to this intent
            if hasattr(order_mgr, '_intents'):
                for oid, managed in order_mgr._orders.items():
                    if managed.intent_group_id == intent_id and oid == order_id:
                        matched_intent = intent
                        matched_intent_id = intent_id
                        break
            if matched_intent:
                break

        # Fallback: match by symbol if not found via intent tracking
        if not matched_intent:
            for intent_id, intent in list(_entry_intents.items()):
                if intent.symbol == symbol and side == intent.side:
                    matched_intent = intent
                    matched_intent_id = intent_id
                    break

        if matched_intent and side == "buy":
            # This is an entry fill — open a position
            pos = position_tracker.open_position(
                symbol=symbol,
                side="long",
                qty=qty,
                avg_price=price,
                tp_price=matched_intent.tp_price,
                sl_price=matched_intent.sl_price,
                entry_order_id=order_id,
                strategy="scanner",
                signal_score=matched_intent.score,
            )

            # Start exit management (places TP order + monitors SL)
            await exit_manager.on_entry_fill(pos)

            # Update circuit breaker
            circuit_breaker.update_position(symbol, pos.notional)

            # Clean up the intent
            if matched_intent_id:
                _entry_intents.pop(matched_intent_id, None)

            logger.info(
                "Entry fill → position opened: %s %s %.6f @ $%.2f TP=$%.2f SL=$%.2f [%s]",
                "LONG", symbol, qty, price, pos.tp_price, pos.sl_price,
                pos.id[:8],
            )

        elif matched_intent and side == "sell":
            # Short entry (future support)
            pos = position_tracker.open_position(
                symbol=symbol,
                side="short",
                qty=qty,
                avg_price=price,
                tp_price=matched_intent.tp_price,
                sl_price=matched_intent.sl_price,
                entry_order_id=order_id,
                strategy="scanner",
                signal_score=matched_intent.score,
            )
            await exit_manager.on_entry_fill(pos)
            circuit_breaker.update_position(symbol, pos.notional)
            if matched_intent_id:
                _entry_intents.pop(matched_intent_id, None)

        # Feed heartbeat on private WS activity
        heartbeat_monitor.heartbeat("private_ws")

    fill_stream.on_fill(_on_fill_routed)
    logger.info("Fill stream → ExitManager/PositionTracker routing enabled")

    # ── 11. Initialize FlushWorker ──
    flush_task = None
    if sb_client:
        from services.flush_worker import FlushWorker

        flush_worker = FlushWorker(store, sb_client, mode=mode)
        flush_task = asyncio.create_task(flush_worker.run_forever())
        logger.info("Flush worker started")
    else:
        logger.warning("No Supabase client — flush worker disabled")

    # ── 12. Main loop: order management tick ──
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for SIGTERM
            pass

    tick_interval = args.tick_interval
    scan_interval = args.scan_interval
    logger.info(
        "=" * 60 + "\n"
        "  ZOE Crypto Trader READY\n"
        "  Mode: %s | Tick: %.1fs | Scan: %.0fs | Pairs: %d\n"
        "  Cash: $%.2f | Holdings: %d\n"
        "  FIFO: %d symbols, $%.2f realized P&L\n"
        "  Scanner: %s\n" +
        "=" * 60,
        mode,
        tick_interval,
        scan_interval,
        len(ws_pairs_list),
        hydration.cash_balance,
        len(hydration.holdings),
        len(fifo.get_all_symbols()),
        fifo.get_realized_pnl(),
        "ENABLED" if scanner else "DISABLED",
    )

    # Write READY event
    store.insert_event(
        mode=mode,
        source="orchestrator",
        type="SYSTEM",
        subtype="READY",
        symbol="",
        body=f"Crypto Trader started (mode={mode}, cash=${hydration.cash_balance:.2f}, {len(hydration.holdings)} positions)",
    )

    import time as _time
    from datetime import timedelta
    last_scan_ts = 0.0
    last_ws_refresh_ts = _time.monotonic()
    last_metric_ts = 0.0
    WS_REFRESH_INTERVAL = 300.0  # Re-subscribe to focus pairs every 5 min
    METRIC_INTERVAL = 60.0       # Emit system health metrics every 60s
    _tick_count = 0
    _tick_durations: list[float] = []

    # ── Daily circuit breaker reset background task ──
    async def _daily_cb_reset() -> None:
        """Reset circuit breaker counters at UTC midnight."""
        while not shutdown_event.is_set():
            try:
                now = datetime.now(timezone.utc)
                next_midnight = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0,
                )
                sleep_secs = (next_midnight - now).total_seconds()
                await asyncio.wait_for(shutdown_event.wait(), timeout=sleep_secs)
                break  # shutdown
            except asyncio.TimeoutError:
                # Midnight reached — reset
                circuit_breaker.reset_daily()
                store.insert_event(
                    mode=mode,
                    source="circuit_breaker",
                    type="RISK",
                    subtype="DAILY_RESET",
                    symbol="",
                    body=f"Daily CB reset (equity=${circuit_breaker.current_equity:.2f})",
                )
                logger.info("Circuit breaker daily reset at UTC midnight")

    daily_reset_task = asyncio.create_task(_daily_cb_reset())

    try:
        while not shutdown_event.is_set():
            try:
                # Order management tick
                await order_mgr.poll_and_manage(
                    get_price=lambda sym: price_cache.snapshot(sym),
                )

                # Exit manager tick: check TP/SL/time-stop for all positions
                await exit_manager.tick()

                # Update position marks (unrealized P&L)
                position_tracker.update_marks(price_cache)

                # Equity update every tick (not just scanner interval)
                tick_equity = hydration.cash_balance + sum(
                    pos.notional for pos in position_tracker.get_open()
                )
                circuit_breaker.update_equity(tick_equity)
            except Exception as e:
                logger.error("Order management tick error: %s", e, exc_info=True)

            _tick_count += 1

            # ── Emit METRIC event for dashboard health indicators ──
            now_mono = _time.monotonic()
            if now_mono - last_metric_ts >= METRIC_INTERVAL:
                try:
                    # Compute sync lag from price cache freshness
                    sync_lag_ms = 0
                    stale_count = 0
                    total_symbols = 0
                    now_ts = _time.time()
                    cache_data = price_cache._cache if hasattr(price_cache, '_cache') else {}
                    for sym in cache_data:
                        total_symbols += 1
                        snap = cache_data.get(sym, {})
                        ts = snap.get("ts", 0)
                        if ts > 0:
                            age_ms = int((now_ts - ts) * 1000)
                            sync_lag_ms = max(sync_lag_ms, age_ms)
                            if age_ms > 30000:  # >30s = stale
                                stale_count += 1

                    stale_quote_rate = (stale_count / total_symbols * 100) if total_symbols > 0 else 0

                    store.insert_event(
                        mode=mode,
                        source="orchestrator",
                        type="SYSTEM",
                        subtype="METRIC",
                        symbol="",
                        body=f"Health: sync_lag={sync_lag_ms}ms stale={stale_quote_rate:.1f}% ticks={_tick_count}",
                        meta={
                            "sync_lag_ms": sync_lag_ms,
                            "stale_quote_rate": round(stale_quote_rate, 1),
                            "spread_blowout_rate": 0,
                            "rejection_rate": 0,
                            "fill_rate": fill_stream.fill_count,
                            "loop_jitter_p99_ms": 0,
                            "total_ticks": _tick_count,
                            "open_positions": position_tracker.position_count(),
                            "active_exits": exit_manager.active_exit_count,
                            "equity": round(tick_equity, 2),
                        },
                    )
                except Exception as e:
                    logger.debug("Metric emission failed: %s", e)
                finally:
                    last_metric_ts = now_mono

            # ── Scanner tick (every scan_interval seconds) ──
            if scanner and now_mono - last_scan_ts >= scan_interval:
                try:
                    candidates = await scanner.scan_candidates()
                    await scanner.write_candidate_scans(candidates)

                    # Refresh holdings from exchange (not stale hydration)
                    open_positions: dict[str, float] = {}
                    try:
                        fresh_holdings = await exchange.get_holdings()
                        if isinstance(fresh_holdings, dict):
                            results = fresh_holdings.get("results", [])
                            if isinstance(results, list):
                                for item in results:
                                    sym = item.get("symbol", "")
                                    qty = float(item.get("quantity_float", item.get("quantity", 0)))
                                    if qty > 1e-8 and sym:
                                        snap = price_cache.snapshot(sym)
                                        mid = snap.get("mid", 0) if snap else 0
                                        open_positions[sym] = qty * mid if mid > 0 else qty
                    except Exception as e:
                        logger.debug("Holdings refresh failed, using hydration: %s", e)
                        # Fallback to hydration data
                        for h_sym, h_qty in hydration.holdings.items():
                            snap = price_cache.snapshot(h_sym)
                            if snap and snap.get("mid", 0) > 0:
                                open_positions[h_sym] = h_qty * snap["mid"]
                            else:
                                open_positions[h_sym] = h_qty

                    # Also include positions from OrderManager in-flight buys
                    for oid, managed in order_mgr._orders.items():
                        if managed.status in ("new", "submitted", "working", "partially_filled"):
                            if managed.symbol not in open_positions:
                                open_positions[managed.symbol] = managed.notional

                    # Refresh cash balance
                    try:
                        balances = await exchange.get_account_balances()
                        if isinstance(balances, dict):
                            for key in ("ZUSD", "USD", "USDT"):
                                if key in balances:
                                    hydration.cash_balance = float(balances[key])
                                    break
                    except Exception:
                        pass  # Use last known cash

                    equity = hydration.cash_balance + sum(open_positions.values())
                    circuit_breaker.update_equity(equity)

                    intents = await scanner.select_trades(
                        candidates, equity, open_positions,
                    )

                    for intent in intents:
                        try:
                            intent_id = await order_mgr.submit_intent(
                                symbol=intent.symbol,
                                side=intent.side,
                                notional=intent.notional,
                                purpose="entry",
                                strategy=intent.strategy,
                                confidence=intent.confidence,
                                order_type=intent.order_type,
                                limit_price=intent.limit_price,
                            )
                            circuit_breaker.record_order()

                            # Track this as an entry intent for fill routing
                            _entry_intents[intent_id] = intent

                            logger.info(
                                "Scanner trade submitted: %s %s $%.2f %s (score=%.0f, intent=%s)",
                                intent.side.upper(),
                                intent.symbol,
                                intent.notional,
                                intent.order_type,
                                intent.score,
                                intent_id[:8],
                            )
                            store.insert_event(
                                mode=mode,
                                source="scanner",
                                type="TRADE",
                                subtype="SUBMIT",
                                symbol=intent.symbol,
                                body=f"Scanner {intent.side.upper()} {intent.symbol} ${intent.notional:.2f} {intent.order_type} (score={intent.score:.0f})",
                                meta={
                                    "intent_id": intent_id,
                                    "score": intent.score,
                                    "side": intent.side,
                                    "notional": intent.notional,
                                    "order_type": intent.order_type,
                                    "limit_price": intent.limit_price,
                                    "sl_price": intent.sl_price,
                                    "tp_price": intent.tp_price,
                                },
                            )
                        except Exception as e:
                            logger.error("Scanner trade submission failed for %s: %s", intent.symbol, e)

                except Exception as e:
                    logger.error("Scanner tick error: %s", e, exc_info=True)
                finally:
                    last_scan_ts = now_mono

            # ── Periodic WS re-subscribe to capture new focus pairs ──
            if scanner and sb_client and now_mono - last_ws_refresh_ts >= WS_REFRESH_INTERVAL:
                try:
                    resp = sb_client.table("market_focus_config").select("symbol").execute()
                    if resp.data:
                        from integrations.kraken_client.symbols import to_kraken
                        new_pairs: list[str] = []
                        for row in resp.data:
                            sym = row.get("symbol", "")
                            if sym:
                                try:
                                    ws_sym = to_kraken(sym, for_ws=True)
                                except Exception:
                                    ws_sym = sym
                                if ws_sym not in ws._ticker_pairs:
                                    new_pairs.append(ws_sym)
                        if new_pairs:
                            await ws.subscribe_ticker(new_pairs)
                            logger.info("WS refresh: subscribed to %d new focus pairs", len(new_pairs))
                except Exception as e:
                    logger.debug("WS focus refresh failed: %s", e)
                finally:
                    last_ws_refresh_ts = now_mono

            # Wait for next tick or shutdown
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(), timeout=tick_interval
                )
            except asyncio.TimeoutError:
                pass  # Normal: tick interval elapsed

    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutting down...")

        # Write shutdown event
        store.insert_event(
            mode=mode,
            source="orchestrator",
            type="SYSTEM",
            subtype="SHUTDOWN",
            symbol="",
            body="Crypto Trader shutting down gracefully",
        )

        # Stop heartbeat monitor
        await heartbeat_monitor.stop()
        logger.info("Heartbeat monitor stopped")

        # Cancel daily reset task
        daily_reset_task.cancel()
        try:
            await daily_reset_task
        except asyncio.CancelledError:
            pass

        # Stop fill stream
        await fill_stream.stop()
        logger.info("Fill stream stopped (processed %d fills)", fill_stream.fill_count)

        # Cancel flush worker
        if flush_task:
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass
            logger.info("Flush worker stopped")

        # Close connections
        await _shutdown(ws, exchange)


async def _shutdown(ws: Any, exchange: Any) -> None:
    """Close WS and REST connections."""
    try:
        await ws.close()
    except Exception:
        pass
    try:
        await exchange.close()
    except Exception:
        pass
    logger.info("Connections closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
