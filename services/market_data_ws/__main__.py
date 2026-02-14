"""Market Data WS Service — entry point.

Startup sequence:
1. Load market catalog from Kraken AssetPairs
2. Determine focus/scout universe
3. Subscribe to WS ticker for both tiers
4. Run coalesced write loop

Usage:
    python -m services.market_data_ws
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv
load_dotenv()
load_dotenv(".env.secrets", override=True)

from .catalog import MarketCatalog
from .coalescer import Coalescer
from .config import MarketDataConfig
from .focus_manager import FocusManager
from .mover_detector import MoverDetector
from .snapshot_writer import SnapshotWriter

logger = logging.getLogger("market_data_ws")


def _setup_logging() -> None:
    level = os.getenv("MD_LOG_LEVEL", "INFO").upper()
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format=fmt)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def _build_exchange_client():
    """Create Kraken client."""
    from integrations.kraken_client import KrakenClient, KrakenConfig
    kraken_key = os.getenv("KRAKEN_API_KEY", "")
    kraken_secret = os.getenv("KRAKEN_API_SECRET", "")
    if not kraken_key or not kraken_secret:
        logger.error("KRAKEN_API_KEY and KRAKEN_API_SECRET required")
        sys.exit(1)
    config = KrakenConfig.from_env()
    return KrakenClient(config)


def _build_supabase():
    """Create Supabase client."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)
    from supabase import create_client
    return create_client(url, key)


async def _run() -> None:
    config = MarketDataConfig()
    exchange = _build_exchange_client()
    sb = _build_supabase()

    logger.info("=" * 60)
    logger.info("MARKET DATA WS SERVICE")
    logger.info("  Focus flush:  %dms", config.focus_flush_ms)
    logger.info("  Scout flush:  %dms", config.scout_flush_ms)
    logger.info("  Default focus: %s", ", ".join(config.default_focus))
    logger.info("=" * 60)

    # ── 1. Catalog: discover all tradable pairs ──
    catalog = MarketCatalog(exchange, sb, quote_filter=config.quote_currency)
    pair_count = await catalog.refresh()
    logger.info("Catalog: %d %s pairs discovered", pair_count, config.quote_currency)

    if pair_count == 0:
        logger.error("No pairs found — cannot start")
        return

    # ── 2. Focus manager: determine universe tiers ──
    focus_mgr = FocusManager(config, sb)
    focus_mgr.set_all_symbols(catalog.get_all_symbols())
    await focus_mgr.load_from_db()

    focus = focus_mgr.focus_symbols
    scout = focus_mgr.scout_symbols
    logger.info("Focus: %d symbols, Scout: %d symbols", len(focus), len(scout))

    # ── 3. Snapshot writer ──
    writer = SnapshotWriter(sb)
    mover_detector = MoverDetector(config)

    # ── 4. Coalescers ──
    focus_coalescer = Coalescer(
        flush_interval_ms=config.focus_flush_ms,
        on_flush=writer.write_focus,
        name="focus",
    )
    scout_coalescer = Coalescer(
        flush_interval_ms=config.scout_flush_ms,
        on_flush=_make_scout_flush(writer, mover_detector, focus_mgr, config),
        name="scout",
    )

    # ── 5. WS connection + subscriptions ──
    from integrations.kraken_client.ws import KrakenWebSocket
    from integrations.kraken_client import KrakenConfig
    from integrations.kraken_client.symbols import from_kraken

    ws_config = KrakenConfig.from_env()
    ws = KrakenWebSocket(ws_config)

    def on_ticker(data: dict) -> None:
        """Handle WS ticker updates — route to focus or scout coalescer."""
        tick_data = data.get("data", [])
        for tick in tick_data:
            ws_symbol = tick.get("symbol", "")
            internal = from_kraken(ws_symbol)

            bid = float(tick.get("bid", 0))
            ask = float(tick.get("ask", 0))
            volume = float(tick.get("volume_24h", tick.get("volume", 0)))
            change = float(tick.get("change_24h", tick.get("change", 0)))
            vwap = float(tick.get("vwap", 0))
            high = float(tick.get("high", 0))
            low = float(tick.get("low", 0))

            kwargs = dict(
                bid=bid, ask=ask, volume_24h=volume,
                change_24h_pct=change, vwap=vwap,
                high_24h=high, low_24h=low,
            )

            if internal in focus_mgr.focus_symbols:
                focus_coalescer.update(internal, **kwargs)
            else:
                scout_coalescer.update(internal, **kwargs)

    ws.on_ticker(on_ticker)

    # Connect and subscribe
    await ws.connect_public()

    # Get WS symbols for all catalog pairs
    all_ws_symbols = catalog.get_ws_symbols()
    if len(all_ws_symbols) > config.max_ws_pairs:
        # Prioritize: focus first, then scout alphabetically
        focus_ws = [s for s in all_ws_symbols if from_kraken(s) in focus]
        scout_ws = [s for s in all_ws_symbols if from_kraken(s) not in focus]
        all_ws_symbols = focus_ws + scout_ws[: config.max_ws_pairs - len(focus_ws)]
        logger.warning(
            "Truncated WS subscriptions to %d (limit=%d)",
            len(all_ws_symbols), config.max_ws_pairs,
        )

    # Subscribe in batches (Kraken limits subscription size)
    batch_size = 50
    for i in range(0, len(all_ws_symbols), batch_size):
        batch = all_ws_symbols[i : i + batch_size]
        await ws.subscribe_ticker(batch)
        logger.info("Subscribed batch %d-%d (%d symbols)", i, i + len(batch), len(batch))

    logger.info("All WS subscriptions active: %d symbols", len(all_ws_symbols))

    # ── 6. Start coalescers ──
    await focus_coalescer.start()
    await scout_coalescer.start()

    # ── 7. Background tasks: sparkline + mover expiry + catalog refresh ──
    sparkline_task = asyncio.create_task(
        _sparkline_loop(focus_coalescer, writer, config)
    )
    expiry_task = asyncio.create_task(
        _mover_expiry_loop(focus_mgr, config)
    )

    logger.info("Market Data WS service running")

    try:
        # Keep running until interrupted
        while True:
            await asyncio.sleep(60)

            # Log stats periodically
            logger.info(
                "Stats: focus=%s scout=%s writer=%s",
                focus_coalescer.stats, scout_coalescer.stats, writer.stats,
            )
    except asyncio.CancelledError:
        pass
    finally:
        sparkline_task.cancel()
        expiry_task.cancel()
        await focus_coalescer.stop()
        await scout_coalescer.stop()
        await ws.close()
        await exchange.close()


def _make_scout_flush(writer, mover_detector, focus_mgr, config):
    """Create scout flush callback that also runs mover detection."""
    async def scout_flush(snapshots):
        await writer.write_scout(snapshots)

        # Run mover detection on scout data
        events = mover_detector.check_movers(snapshots)
        for event in events:
            await writer.write_mover(
                symbol=event["symbol"],
                event_type=event["event_type"],
                magnitude=event["magnitude"],
                direction=event["direction"],
                metadata=event.get("metadata"),
            )
            # Promote to focus
            focus_mgr.promote(
                event["symbol"],
                reason="mover",
                ttl_minutes=config.mover_focus_minutes,
            )

    return scout_flush


async def _sparkline_loop(
    focus_coalescer: Coalescer,
    writer: SnapshotWriter,
    config: MarketDataConfig,
) -> None:
    """Write sparkline points for focus symbols at regular intervals."""
    while True:
        try:
            await asyncio.sleep(config.sparkline_interval_sec)
            for symbol, snap in focus_coalescer.get_all().items():
                if snap.mid > 0:
                    await writer.write_sparkline(symbol, snap.mid)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Sparkline loop error: %s", e)


async def _mover_expiry_loop(focus_mgr: FocusManager, config: MarketDataConfig) -> None:
    """Periodically expire stale movers from focus."""
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            demoted = focus_mgr.expire_stale_movers()
            if demoted:
                logger.info("Expired %d stale movers from focus", demoted)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Mover expiry error: %s", e)


def main() -> None:
    _setup_logging()
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Shutting down (KeyboardInterrupt)")


if __name__ == "__main__":
    main()
