"""Smoke tests for Kraken REST + WebSocket connectivity.

Usage:
    python -m integrations.kraken_client.test_connectivity [test_name]

Tests:
    system_status    — Public endpoint, no auth needed
    tradable_pairs   — Public, discovers all pairs
    balance          — Private, confirms API keys work
    open_orders      — Private, lists open orders
    ws_public        — Subscribe to BTC/USD ticker, receive 1 message
    ws_private       — Get auth token, subscribe to executions
    all              — Run all tests (default)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kraken_smoke_test")


def _mask(value: str, show: int = 4) -> str:
    if len(value) <= show:
        return "****"
    return f"****{value[-show:]}"


async def test_system_status() -> bool:
    """Test: Kraken system status (public, no auth)."""
    from integrations.kraken_client import KrakenClient, KrakenConfig

    config = KrakenConfig(api_key="", api_secret="")  # No auth needed
    config.base_url = "https://api.kraken.com"
    client = KrakenClient(config)

    try:
        result = await client.get_system_status()
        status = result.get("status", "unknown")
        timestamp = result.get("timestamp", "")
        logger.info("Kraken system status: %s (at %s)", status, timestamp)
        await client.close()
        return status == "online"
    except Exception as e:
        logger.error("System status FAILED: %s", e)
        await client.close()
        return False


async def test_tradable_pairs() -> bool:
    """Test: Discover tradable pairs (public, no auth)."""
    from integrations.kraken_client import KrakenClient, KrakenConfig

    config = KrakenConfig(api_key="", api_secret="")
    client = KrakenClient(config)

    try:
        result = await client.get_trading_pairs()
        count = len(result)
        logger.info("Found %d tradable pairs", count)

        # Show a few examples
        samples = list(result.keys())[:5]
        for pair in samples:
            info = result[pair]
            logger.info(
                "  %s: base=%s quote=%s wsname=%s",
                pair,
                info.get("base", "?"),
                info.get("quote", "?"),
                info.get("wsname", "?"),
            )

        await client.close()
        return count > 50  # Kraken has 600+ pairs
    except Exception as e:
        logger.error("Tradable pairs FAILED: %s", e)
        await client.close()
        return False


async def test_balance() -> bool:
    """Test: Get account balance (private, requires API keys)."""
    from integrations.kraken_client import KrakenClient, KrakenConfig

    config = KrakenConfig.from_env()
    client = KrakenClient(config)

    try:
        result = await client.get_account_balances()
        assets = [(k, float(v)) for k, v in result.items() if float(v) > 0]
        logger.info("Balance retrieved successfully (%d assets with balance)", len(assets))
        for asset, qty in sorted(assets, key=lambda x: -x[1])[:5]:
            logger.info("  %s: %.8f", asset, qty)

        await client.close()
        return True
    except Exception as e:
        logger.error("Balance FAILED: %s", e)
        await client.close()
        return False


async def test_open_orders() -> bool:
    """Test: Get open orders (private)."""
    from integrations.kraken_client import KrakenClient, KrakenConfig

    config = KrakenConfig.from_env()
    client = KrakenClient(config)

    try:
        result = await client.get_open_orders()
        count = len(result)
        logger.info("Open orders retrieved (%d orders)", count)
        for order_id, order in list(result.items())[:3]:
            descr = order.get("descr", {})
            logger.info(
                "  %s: %s %s %s @ %s",
                order_id[:12],
                descr.get("type", "?"),
                descr.get("pair", "?"),
                descr.get("ordertype", "?"),
                descr.get("price", "?"),
            )

        await client.close()
        return True
    except Exception as e:
        logger.error("Open orders FAILED: %s", e)
        await client.close()
        return False


async def test_ws_public() -> bool:
    """Test: Public WS ticker subscription — receive 1 BTC/USD tick."""
    from integrations.kraken_client.ws import KrakenWebSocket
    from integrations.kraken_client import KrakenConfig

    config = KrakenConfig(api_key="", api_secret="")
    ws = KrakenWebSocket(config)

    received_event = asyncio.Event()
    received_data: list[dict] = []

    def on_tick(data: dict) -> None:
        received_data.append(data)
        received_event.set()

    ws.on_ticker(on_tick)

    try:
        await ws.connect_public()
        await ws.subscribe_ticker(["BTC/USD"])
        logger.info("Subscribed to XBT/USD ticker, waiting for data...")

        try:
            await asyncio.wait_for(received_event.wait(), timeout=15)
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for ticker data (15s)")
            await ws.close()
            return False

        if received_data:
            tick = received_data[0]
            logger.info("WS public ticker received for BTC/USD: channel=%s type=%s",
                        tick.get("channel", "?"), tick.get("type", "?"))
            await ws.close()
            return True

        await ws.close()
        return False

    except Exception as e:
        logger.error("WS public FAILED: %s", e)
        await ws.close()
        return False


async def test_ws_private() -> bool:
    """Test: Private WS auth — get token and subscribe to executions."""
    from integrations.kraken_client import KrakenClient, KrakenConfig
    from integrations.kraken_client.ws import KrakenWebSocket

    config = KrakenConfig.from_env()
    client = KrakenClient(config)

    try:
        # Get WS auth token
        token = await client.get_ws_token()
        logger.info("WS auth token obtained (length=%d)", len(token))

        ws = KrakenWebSocket(config)

        sub_event = asyncio.Event()
        sub_data: list[dict] = []

        def on_exec(data: dict) -> None:
            sub_data.append(data)
            sub_event.set()

        ws.on_execution(on_exec)

        await ws.connect_private(token)
        logger.info("Private WS connected, waiting for executions snapshot...")

        try:
            await asyncio.wait_for(sub_event.wait(), timeout=15)
        except asyncio.TimeoutError:
            # It's OK if no executions arrive — subscription may still succeed
            logger.info("No execution events in 15s (this is normal if no recent trades)")

        await ws.close()
        await client.close()

        logger.info(
            "WS private auth token obtained, subscribed to executions (%d events received)",
            len(sub_data),
        )
        return True

    except Exception as e:
        logger.error("WS private FAILED: %s", e)
        await client.close()
        return False


async def run_all() -> dict[str, bool]:
    """Run all connectivity tests."""
    results: dict[str, bool] = {}

    tests = [
        ("system_status", test_system_status),
        ("tradable_pairs", test_tradable_pairs),
        ("balance", test_balance),
        ("open_orders", test_open_orders),
        ("ws_public", test_ws_public),
        ("ws_private", test_ws_private),
    ]

    for name, test_fn in tests:
        logger.info("=" * 60)
        logger.info("Running test: %s", name)
        logger.info("=" * 60)
        try:
            results[name] = await test_fn()
        except Exception as e:
            logger.error("Test %s crashed: %s", name, e)
            results[name] = False
        logger.info("Result: %s → %s", name, "PASS" if results[name] else "FAIL")
        logger.info("")

    return results


def main() -> None:
    # Load .env from project root
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    load_dotenv(os.path.join(root, ".env"))

    test_name = sys.argv[1] if len(sys.argv) > 1 else "all"

    test_map = {
        "system_status": test_system_status,
        "tradable_pairs": test_tradable_pairs,
        "balance": test_balance,
        "open_orders": test_open_orders,
        "ws_public": test_ws_public,
        "ws_private": test_ws_private,
    }

    if test_name == "all":
        results = asyncio.run(run_all())
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        logger.info("=" * 60)
        logger.info("SUMMARY: %d/%d tests passed", passed, total)
        for name, ok in results.items():
            logger.info("  %s: %s", name, "PASS" if ok else "FAIL")
        sys.exit(0 if passed == total else 1)
    elif test_name in test_map:
        ok = asyncio.run(test_map[test_name]())
        logger.info("Result: %s → %s", test_name, "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    else:
        print(f"Unknown test: {test_name}")
        print(f"Available: {', '.join(test_map.keys())}, all")
        sys.exit(1)


if __name__ == "__main__":
    main()
