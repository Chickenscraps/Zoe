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
    # Normalize pair format for WS (e.g., "BTC/USD")
    ws_pairs = [p.strip() for p in args.pairs if p.strip()]
    if ws_pairs:
        await ws.subscribe_ticker(ws_pairs)
        logger.info("Subscribed to tickers: %s", ws_pairs)

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
    logger.info(
        "=" * 60 + "\n"
        "  ZOE Crypto Trader READY\n"
        "  Mode: %s | Tick: %.1fs | Pairs: %s\n"
        "  Cash: $%.2f | Holdings: %d\n"
        "  FIFO: %d symbols, $%.2f realized P&L\n" +
        "=" * 60,
        mode,
        tick_interval,
        ", ".join(ws_pairs),
        hydration.cash_balance,
        len(hydration.holdings),
        len(fifo.get_all_symbols()),
        fifo.get_realized_pnl(),
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

    try:
        while not shutdown_event.is_set():
            try:
                # Order management tick
                await order_mgr.poll_and_manage(
                    get_price=lambda sym: price_cache.snapshot(sym),
                )
            except Exception as e:
                logger.error("Order management tick error: %s", e, exc_info=True)

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
