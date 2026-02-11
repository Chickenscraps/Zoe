"""
Edge Factory Runner — wires all components and starts the trading loop.

Usage:
    # Paper mode (recommended first):
    EDGE_FACTORY_MODE=paper python -m services.edge_factory.runner

    # Live mode (requires confirmation phrase):
    EDGE_FACTORY_MODE=live python -m services.edge_factory.runner

    # Dry-run: just verify wiring, don't start the loop:
    python -m services.edge_factory.runner --dry-run
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# Load .env before any config reads
from dotenv import load_dotenv

load_dotenv()

from .account_state import AccountState
from .config import CONFIRM_PHRASE, EdgeFactoryConfig
from .execution_policy import ExecutionPolicyEngine
from .feature_engine import FeatureEngine
from .features import ALL_FEATURES
from .ingestion import GoogleTrendsIngestor, MarketDataIngestor, OKXFundingIngestor
from .order_manager import OrderManager
from .orchestrator import EdgeFactoryOrchestrator
from .paper_executor import PaperExecutor
from .position_sizer import PositionSizer
from .quote_model import QuoteModel
from .regime_detector import RegimeDetector
from .repository import InMemoryFeatureRepository, SupabaseFeatureRepository
from .signal_generator import SignalGenerator
from .trade_intent import TradeIntentBuilder

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
        logger.info("Using Supabase repository")
        return SupabaseFeatureRepository()

    logger.warning("No Supabase credentials -- falling back to in-memory repository")
    return InMemoryFeatureRepository()


def _build_rh_client():
    """Create RobinhoodCryptoClient if credentials exist."""
    api_key = os.getenv("RH_CRYPTO_API_KEY", "")
    seed = os.getenv("RH_CRYPTO_PRIVATE_KEY_SEED", "")

    if not api_key or not seed:
        return None

    from integrations.robinhood_crypto_client.client import (
        RobinhoodCryptoClient,
        RobinhoodCryptoConfig,
    )

    rh_config = RobinhoodCryptoConfig.from_env()
    return RobinhoodCryptoClient(rh_config)


def _build_polygon_client():
    """Create Polygon MarketData client if API key exists."""
    if not os.getenv("POLYGON_API_KEY", ""):
        return None

    from market_data import MarketData

    return MarketData()


def _build_executor(config, repo, rh_client):
    """Build the right executor for the current mode."""
    if config.is_live():
        if rh_client is None:
            logger.error("Live mode requires RH_CRYPTO_API_KEY + RH_CRYPTO_PRIVATE_KEY_SEED")
            sys.exit(1)

        from .live_executor import LiveExecutor

        # Wire V2 execution quality layer if RH client is available
        quote_model = QuoteModel(rh_client, config)
        exec_policy = ExecutionPolicyEngine(config)
        order_mgr = OrderManager(rh_client, quote_model, config)

        return LiveExecutor(
            config, repo, rh_client,
            quote_model=quote_model,
            execution_policy=exec_policy,
            order_manager=order_mgr,
        )

    # Paper mode
    return PaperExecutor(config, repo)


def build_orchestrator(config: EdgeFactoryConfig | None = None) -> EdgeFactoryOrchestrator:
    """
    Wire all components and return a ready-to-run orchestrator.

    Public so tests / Discord bot can reuse the wiring logic.
    """
    if config is None:
        config = EdgeFactoryConfig()

    repo = _build_repository(config)
    rh_client = _build_rh_client()
    polygon_client = _build_polygon_client()

    # ── Ingestors ──────────────────────────────────────────
    ingestors = {}

    market_ingestor = MarketDataIngestor(config, polygon_client, rh_client)
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
    executor = _build_executor(config, repo, rh_client)

    # ── V2 optional components ─────────────────────────────
    account_state = AccountState(config, repo, rh_client)
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
    orchestrator._rh_client = rh_client  # type: ignore[attr-defined]

    return orchestrator


async def _cleanup(orchestrator: EdgeFactoryOrchestrator) -> None:
    """Close aiohttp sessions and RH client."""
    for name, ing in getattr(orchestrator, "_closeable_ingestors", {}).items():
        if hasattr(ing, "close"):
            try:
                await ing.close()
            except Exception:
                pass

    rh = getattr(orchestrator, "_rh_client", None)
    if rh is not None and hasattr(rh, "close"):
        try:
            await rh.close()
        except Exception:
            pass


async def _run(dry_run: bool = False) -> None:
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
        logger.error("EDGE_FACTORY_MODE is '%s'. Set to 'paper' or 'live' to start.", config.mode)
        return

    # Live mode safety gate
    if config.is_live():
        confirm = os.getenv("RH_LIVE_CONFIRM", "")
        if confirm != CONFIRM_PHRASE:
            logger.error(
                "Live mode requires RH_LIVE_CONFIRM='%s'",
                CONFIRM_PHRASE,
            )
            return

    orchestrator = build_orchestrator(config)

    try:
        if dry_run:
            logger.info("Dry-run: running one tick...")
            summary = await orchestrator.tick()
            logger.info("Tick result: %s", summary)
            logger.info("Dry-run complete. Wiring OK.")
            return

        logger.info("Starting run_forever loop...")
        await orchestrator.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down (KeyboardInterrupt)")
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
    finally:
        await _cleanup(orchestrator)


def main() -> None:
    _setup_logging()

    # Ensure logs directory exists for JsonAuditLogger
    os.makedirs("logs", exist_ok=True)

    dry_run = "--dry-run" in sys.argv
    asyncio.run(_run(dry_run=dry_run))


if __name__ == "__main__":
    main()
