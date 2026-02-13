"""
Edge Factory Runner — wires all components and starts the trading loop.

Usage:
    EDGE_FACTORY_MODE=live python -m services.edge_factory.runner

    # Dry-run: just verify wiring, don't start the loop:
    python -m services.edge_factory.runner --dry-run
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# Load .env + .env.secrets before any config reads
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.secrets", override=True)

from .account_state import AccountState
from .config import CONFIRM_PHRASE, EdgeFactoryConfig
from .execution_policy import ExecutionPolicyEngine
from .feature_engine import FeatureEngine
from .features import ALL_FEATURES
from .ingestion import GoogleTrendsIngestor, MarketDataIngestor, OKXFundingIngestor
from .order_manager import OrderManager
from .orchestrator import EdgeFactoryOrchestrator
from .position_sizer import PositionSizer
from .quote_model import QuoteModel
from .regime_detector import RegimeDetector
from .repository import InMemoryFeatureRepository, SupabaseFeatureRepository
from .signal_generator import SignalGenerator
from .trade_intent import TradeIntentBuilder

# Local-first event store + flush worker
from services.local_store import LocalEventStore
from services.flush_worker import FlushWorker

# Highlander rule: process-level instance lock
from services.instance_lock import InstanceLock, InstanceAlreadyRunning

# Rate limiter for exchange API calls
from services.rate_limiter import RateLimitManager

# Circuit breakers + metrics
from .circuit_breakers import CircuitBreakerManager
from .metrics_collector import MetricsCollector

logger = logging.getLogger("edge_factory")


def _setup_logging() -> None:
    """Configure structured logging for the bot."""
    level = os.getenv("EF_LOG_LEVEL", "INFO").upper()
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format=fmt)
    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pytrends").setLevel(logging.WARNING)


def _build_repository(config: EdgeFactoryConfig):
    """Choose persistence backend based on env vars."""
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if supabase_url and supabase_key:
        logger.info("Using Supabase repository (mode=%s)", config.mode)
        return SupabaseFeatureRepository(mode=config.mode)

    logger.warning("No Supabase credentials -- falling back to in-memory repository")
    return InMemoryFeatureRepository()


def _build_exchange_client():
    """Create Kraken exchange client (or None if no creds)."""
    kraken_key = os.getenv("KRAKEN_API_KEY", "")
    kraken_secret = os.getenv("KRAKEN_API_SECRET", "")
    if not kraken_key or not kraken_secret:
        logger.warning("KRAKEN_API_KEY/SECRET not set")
        return None
    from integrations.kraken_client import KrakenClient, KrakenConfig
    config = KrakenConfig.from_env()
    return KrakenClient(config)


def _build_polygon_client():
    """Create Polygon MarketData client if API key exists."""
    if not os.getenv("POLYGON_API_KEY", ""):
        return None

    from market_data import MarketData

    return MarketData()


def _build_executor(config, repo, exchange_client):
    """Build the live executor."""
    if exchange_client is None:
        logger.error("Live mode requires Kraken API credentials")
        sys.exit(1)

    from .live_executor import LiveExecutor

    quote_model = QuoteModel(exchange_client, config)
    exec_policy = ExecutionPolicyEngine(config)
    order_mgr = OrderManager(exchange_client, quote_model, config)

    return LiveExecutor(
        config, repo, exchange_client,
        quote_model=quote_model,
        execution_policy=exec_policy,
        order_manager=order_mgr,
    )


def build_orchestrator(config: EdgeFactoryConfig | None = None) -> EdgeFactoryOrchestrator:
    """
    Wire all components and return a ready-to-run orchestrator.

    Public so tests / Discord bot can reuse the wiring logic.
    """
    if config is None:
        config = EdgeFactoryConfig()

    repo = _build_repository(config)
    exchange_client = _build_exchange_client()
    polygon_client = _build_polygon_client()

    # ── Ingestors ──────────────────────────────────────────
    ingestors = {}

    market_ingestor = MarketDataIngestor(config, polygon_client, exchange_client)
    ingestors["polygon"] = market_ingestor

    try:
        trends_ingestor = GoogleTrendsIngestor(config)
        ingestors["google_trends"] = trends_ingestor
    except Exception as e:
        logger.warning("Google Trends ingestor failed to init: %s", e)

    try:
        okx_ingestor = OKXFundingIngestor(config)
        ingestors["okx"] = okx_ingestor
    except Exception as e:
        logger.warning("OKX funding ingestor failed to init: %s", e)

    # ── Core components ────────────────────────────────────
    feature_engine = FeatureEngine(config, repo, ingestors, list(ALL_FEATURES))
    regime_detector = RegimeDetector(config, repo)
    signal_generator = SignalGenerator(config, regime_detector)
    position_sizer = PositionSizer(config, repo)
    executor = _build_executor(config, repo, exchange_client)

    # ── V2 optional components ─────────────────────────────
    account_state = AccountState(config, repo, exchange_client)
    trade_intent = TradeIntentBuilder(config, position_sizer, repo)

    # ── Orchestrator ───────────────────────────────────────
    orchestrator = EdgeFactoryOrchestrator(
        config=config,
        feature_engine=feature_engine,
        regime_detector=regime_detector,
        signal_generator=signal_generator,
        position_sizer=position_sizer,
        executor=executor,
        repository=repo,
        trade_intent_builder=trade_intent,
        account_state=account_state,
    )

    # Stash closeable resources for graceful shutdown
    orchestrator._closeable_ingestors = ingestors  # type: ignore[attr-defined]
    orchestrator._exchange_client = exchange_client  # type: ignore[attr-defined]

    return orchestrator


async def _cleanup(orchestrator: EdgeFactoryOrchestrator) -> None:
    """Close aiohttp sessions and exchange client."""
    for name, ing in getattr(orchestrator, "_closeable_ingestors", {}).items():
        if hasattr(ing, "close"):
            try:
                await ing.close()
            except Exception:
                pass

    exchange = getattr(orchestrator, "_exchange_client", None)
    if exchange is not None and hasattr(exchange, "close"):
        try:
            await exchange.close()
        except Exception:
            pass


async def _run(dry_run: bool = False, instance_lock: InstanceLock | None = None) -> None:
    """Main async entry point."""
    config = EdgeFactoryConfig()

    logger.info("=" * 60)
    logger.info("EDGE FACTORY v2")
    logger.info("  Mode:    %s", config.mode)
    logger.info("  Symbols: %s", ", ".join(config.symbols))
    logger.info("  Equity:  $%.2f", config.account_equity)
    logger.info("  Tick:    %ds", config.market_poll_interval)
    logger.info("=" * 60)

    if not config.is_active():
        logger.error("EDGE_FACTORY_MODE is '%s'. Set to 'live' to start.", config.mode)
        return

    # Safety gate
    confirm = os.getenv("LIVE_CONFIRM", "")
    if confirm != CONFIRM_PHRASE:
        logger.error(
            "Live mode requires LIVE_CONFIRM='%s'",
            CONFIRM_PHRASE,
        )
        return

    # ── Rate limiter for exchange API ──────────────────────
    rate_limiter = RateLimitManager(
        rpm=int(os.getenv("EXCHANGE_RATE_LIMIT_RPM", "100")),
        burst=int(os.getenv("EXCHANGE_RATE_LIMIT_BURST", "150")),
        backoff_seconds=float(os.getenv("EXCHANGE_RATE_LIMIT_BACKOFF", "30")),
    )

    orchestrator = build_orchestrator(config)

    # ── Circuit breakers ───────────────────────────────────
    circuit_breakers = CircuitBreakerManager(
        dd_soft_pct=float(os.getenv("CB_DD_SOFT_PCT", "5.0")),
        dd_hard_pct=float(os.getenv("CB_DD_HARD_PCT", "20.0")),
        max_consecutive_losses=int(os.getenv("CB_MAX_CONSEC_LOSSES", "5")),
        loss_cooldown_hours=float(os.getenv("CB_LOSS_COOLDOWN_HOURS", "4.0")),
        spread_blowout_pct=float(os.getenv("CB_SPREAD_BLOWOUT_PCT", "1.0")),
    )

    # ── Metrics collector ──────────────────────────────────
    metrics_collector = MetricsCollector(
        emit_interval_ticks=int(os.getenv("METRICS_EMIT_INTERVAL", "10")),
    )

    # Stash on orchestrator for access by sub-components
    orchestrator._rate_limiter = rate_limiter  # type: ignore[attr-defined]
    orchestrator._circuit_breakers = circuit_breakers  # type: ignore[attr-defined]
    orchestrator._metrics = metrics_collector  # type: ignore[attr-defined]

    # ── Local-first event store + flush worker ─────────────
    local_store = None
    flush_task = None
    try:
        store_path = os.getenv("LOCAL_STORE_PATH", "data/local_events.db")
        local_store = LocalEventStore(store_path)
        logger.info("Local event store initialized: %s", store_path)

        # Create Supabase client for flush worker
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if supabase_url and supabase_key:
            from supabase import create_client
            flush_sb = create_client(supabase_url, supabase_key)
            flush_worker = FlushWorker(local_store, flush_sb, mode=config.mode)
            logger.info("Flush worker created (mode=%s)", config.mode)
        else:
            flush_worker = None
            logger.warning("No Supabase credentials — flush worker disabled")
    except Exception as e:
        logger.warning("Failed to init local store / flush worker: %s", e)
        flush_worker = None

    # Stash local_store on orchestrator for event emission
    orchestrator._local_store = local_store  # type: ignore[attr-defined]
    orchestrator._flush_worker = flush_worker  # type: ignore[attr-defined]

    # Stash Supabase client on orchestrator for health heartbeats
    sb_client = getattr(flush_worker, 'sb', None) if flush_worker else None
    orchestrator._supabase = sb_client  # type: ignore[attr-defined]

    # Wire Supabase client into AccountState for mark-to-market lookups
    if sb_client and hasattr(orchestrator, 'account_state') and orchestrator.account_state is not None:
        orchestrator.account_state._sb = sb_client  # type: ignore[attr-defined]

    # C3: Stash metrics + local_store on executor for IS tracking
    executor = orchestrator.executor
    executor._metrics = metrics_collector  # type: ignore[attr-defined]
    executor._local_store = local_store  # type: ignore[attr-defined]

    try:
        if dry_run:
            logger.info("Dry-run: running one tick...")
            summary = await orchestrator.tick()
            logger.info("Tick result: %s", summary)
            logger.info("Dry-run complete. Wiring OK.")
            return

        # Start flush worker alongside the trading loop
        if flush_worker is not None:
            flush_task = asyncio.create_task(flush_worker.run_forever())
            logger.info("Flush worker started as background task")

        logger.info("Starting run_forever loop...")
        await orchestrator.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down (KeyboardInterrupt)")
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
    finally:
        # Cancel flush worker gracefully
        if flush_task is not None:
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass

        # Close local store
        if local_store is not None:
            local_store.close()

        await _cleanup(orchestrator)


def main() -> None:
    _setup_logging()

    # Ensure logs directory exists for JsonAuditLogger
    os.makedirs("logs", exist_ok=True)

    dry_run = "--dry-run" in sys.argv

    # ── Highlander Rule: only one bot instance ──────────────
    lock_path = os.getenv("EF_LOCK_PATH", "data/edge_factory.lock")
    instance_lock = InstanceLock(lock_path)
    try:
        instance_lock.acquire()
    except InstanceAlreadyRunning as e:
        logger.critical(str(e))
        sys.exit(1)

    try:
        asyncio.run(_run(dry_run=dry_run, instance_lock=instance_lock))
    finally:
        instance_lock.release()


if __name__ == "__main__":
    main()
