"""Crypto Snapshots Service — bridges Kraken balances to Supabase.

Runs every 5 minutes to write:
- Cash snapshots   → crypto_cash_snapshots  (buying_power for equity chart)
- Holdings snapshots → crypto_holdings_snapshots (positions + total USD value)
- Heartbeat        → health_heartbeat       (dashboard shows service is alive)

Cleanup: Deletes snapshots older than 90 days once per day.

Usage:
    python -m services.crypto_snapshots
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.secrets", override=True)

logger = logging.getLogger("crypto_snapshots")

# ── Config ──────────────────────────────────────────────────────────────
SNAPSHOT_INTERVAL_SEC = int(os.getenv("SNAPSHOT_INTERVAL_SEC", "300"))  # 5 min
RETENTION_DAYS = 90
CLEANUP_INTERVAL_SEC = 24 * 60 * 60  # once per day
MODE = os.getenv("TRADING_MODE", "live")
INSTANCE_ID = os.getenv("INSTANCE_ID", "default")


# ── Setup ───────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    level = os.getenv("SNAP_LOG_LEVEL", "INFO").upper()
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format=fmt)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _build_supabase():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)
    from supabase import create_client
    return create_client(url, key)


def _build_exchange_client():
    from integrations.kraken_client import KrakenClient, KrakenConfig
    kraken_key = os.getenv("KRAKEN_API_KEY", "")
    kraken_secret = os.getenv("KRAKEN_API_SECRET", "")
    if not kraken_key or not kraken_secret:
        logger.error("KRAKEN_API_KEY and KRAKEN_API_SECRET required")
        sys.exit(1)
    config = KrakenConfig.from_env()
    return KrakenClient(config)


# ── Snapshot writers ────────────────────────────────────────────────────

async def _write_cash_snapshot(sb: Any, exchange: Any) -> None:
    """Fetch USD balance from Kraken → insert into crypto_cash_snapshots."""
    try:
        balances = await exchange.get_account_balances()

        # Kraken uses "ZUSD" for USD; fallback to "USD"
        usd = 0.0
        for key in ("ZUSD", "USD"):
            if key in balances:
                usd = float(balances[key])
                break

        if not math.isfinite(usd):
            usd = 0.0

        now = datetime.now(timezone.utc).isoformat()
        sb.table("crypto_cash_snapshots").insert({
            "cash_available": usd,
            "buying_power": usd,
            "mode": MODE,
            "taken_at": now,
        }).execute()

        logger.info("Cash snapshot: $%.2f", usd)
    except Exception as e:
        logger.error("Cash snapshot failed: %s", e, exc_info=True)


async def _write_holdings_snapshot(sb: Any, exchange: Any, converter: Any) -> None:
    """Fetch crypto holdings from Kraken → insert into crypto_holdings_snapshots."""
    try:
        resp = await exchange.get_holdings()
        results = resp.get("results", [])

        # Build holdings dict: {"BTC-USD": 0.5, "ETH-USD": 1.2}
        holdings_dict: dict[str, float] = {}
        balances_for_converter: dict[str, float] = {}

        for h in results:
            symbol = h["symbol"]        # already normalized by get_holdings()
            asset = h["asset"]          # e.g. "BTC"
            qty = h.get("quantity_float", 0.0)

            if not math.isfinite(qty) or qty <= 0:
                continue

            holdings_dict[symbol] = qty
            balances_for_converter[asset] = qty

        # Mark-to-market via USDConverter
        total_value = 0.0
        if balances_for_converter:
            total_value = await converter.total_usd(balances_for_converter)

        if not math.isfinite(total_value):
            total_value = 0.0

        now = datetime.now(timezone.utc).isoformat()
        sb.table("crypto_holdings_snapshots").insert({
            "holdings": holdings_dict,
            "total_crypto_value": total_value,
            "mode": MODE,
            "taken_at": now,
        }).execute()

        logger.info(
            "Holdings snapshot: %d assets, $%.2f total",
            len(holdings_dict), total_value,
        )
    except Exception as e:
        logger.error("Holdings snapshot failed: %s", e, exc_info=True)


async def _write_heartbeat(
    sb: Any,
    status: str = "ok",
    message: str = "Snapshots running",
) -> None:
    """Upsert heartbeat so the dashboard knows we're alive."""
    try:
        sb.table("health_heartbeat").upsert({
            "instance_id": INSTANCE_ID,
            "component": "crypto_snapshots",
            "status": status,
            "message": message,
            "mode": MODE,
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="instance_id,component,mode").execute()
    except Exception as e:
        logger.warning("Heartbeat write failed: %s", e)


# ── Cleanup ─────────────────────────────────────────────────────────────

async def _cleanup_old_snapshots(sb: Any) -> None:
    """Delete snapshots older than RETENTION_DAYS to prevent table bloat."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()

        r1 = sb.table("crypto_cash_snapshots").delete().lt("taken_at", cutoff).execute()
        r2 = sb.table("crypto_holdings_snapshots").delete().lt("taken_at", cutoff).execute()

        n1 = len(r1.data) if r1.data else 0
        n2 = len(r2.data) if r2.data else 0
        if n1 or n2:
            logger.info("Cleanup: removed %d cash + %d holdings snapshots", n1, n2)
    except Exception as e:
        logger.error("Cleanup failed: %s", e, exc_info=True)


# ── Main loop ───────────────────────────────────────────────────────────

async def _take_snapshot(sb: Any, exchange: Any, converter: Any) -> None:
    """Single snapshot tick — writes cash, holdings, and heartbeat."""
    await _write_cash_snapshot(sb, exchange)
    await _write_holdings_snapshot(sb, exchange, converter)
    await _write_heartbeat(sb)


async def _run() -> None:
    exchange = _build_exchange_client()
    sb = _build_supabase()

    from integrations.kraken_client import USDConverter
    converter = USDConverter(exchange)

    logger.info("=" * 60)
    logger.info("CRYPTO SNAPSHOTS SERVICE")
    logger.info("  Mode:     %s", MODE)
    logger.info("  Interval: %ds", SNAPSHOT_INTERVAL_SEC)
    logger.info("  Retain:   %d days", RETENTION_DAYS)
    logger.info("=" * 60)

    last_cleanup = datetime.now(timezone.utc)

    try:
        # First snapshot immediately
        await _take_snapshot(sb, exchange, converter)

        while True:
            await asyncio.sleep(SNAPSHOT_INTERVAL_SEC)
            await _take_snapshot(sb, exchange, converter)

            # Daily cleanup
            now = datetime.now(timezone.utc)
            if (now - last_cleanup).total_seconds() >= CLEANUP_INTERVAL_SEC:
                await _cleanup_old_snapshots(sb)
                last_cleanup = now

    except asyncio.CancelledError:
        logger.info("Shutdown requested")
        await _write_heartbeat(sb, "down", "Service stopped")
    except Exception as e:
        logger.error("Fatal: %s", e, exc_info=True)
        await _write_heartbeat(sb, "error", f"Fatal: {e}")
        raise
    finally:
        await exchange.close()
        logger.info("Crypto snapshots service stopped")


def main() -> None:
    _setup_logging()
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Shutting down (KeyboardInterrupt)")


if __name__ == "__main__":
    main()
