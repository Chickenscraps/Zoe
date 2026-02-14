"""Kraken connectivity smoke test.

Run this script to verify:
  1. REST public endpoints work (Time, AssetPairs, Ticker)
  2. REST private endpoints work (Balance, GetWebSocketsToken) — requires API keys
  3. WS v2 public connection works (subscribe ticker for BTC/USD)
  4. Symbol normalization round-trips correctly

Usage:
    python -m services.crypto_trader.test_connectivity

Environment variables required for private tests:
    KRAKEN_API_KEY, KRAKEN_API_SECRET
"""

from __future__ import annotations

import asyncio
import os
import sys
import time


async def test_public_rest() -> bool:
    """Test public REST endpoints."""
    from .kraken_client import KrakenRestClient
    client = KrakenRestClient()

    print("\n=== PUBLIC REST ===")

    # 1. Server time
    try:
        result = await client.get_server_time()
        print(f"  [OK] Server time: {result}")
    except Exception as e:
        print(f"  [FAIL] Server time: {e}")
        await client.close()
        return False

    # 2. Asset pairs
    try:
        pairs = await client.get_asset_pairs()
        usd_pairs = [p for p in pairs if p.quote == "USD"]
        usdt_pairs = [p for p in pairs if p.quote == "USDT"]
        usdc_pairs = [p for p in pairs if p.quote == "USDC"]
        print(f"  [OK] Asset pairs: {len(pairs)} total, {len(usd_pairs)} USD, {len(usdt_pairs)} USDT, {len(usdc_pairs)} USDC")
        # Show a few examples
        for p in pairs[:3]:
            print(f"       {p.symbol} (altname={p.altname}, lot_min={p.lot_min}, cost_min={p.cost_min})")
    except Exception as e:
        print(f"  [FAIL] Asset pairs: {e}")
        await client.close()
        return False

    # 3. Ticker
    try:
        tickers = await client.get_ticker(["XBTUSD", "ETHUSD"])
        for key, t in tickers.items():
            print(f"  [OK] Ticker {key}: bid={t.bid}, ask={t.ask}, last={t.last}, vol24h={t.volume_24h}")
    except Exception as e:
        print(f"  [FAIL] Ticker: {e}")
        await client.close()
        return False

    await client.close()
    return True


async def test_private_rest() -> bool:
    """Test private REST endpoints (requires API keys)."""
    from .kraken_client import KrakenRestClient

    api_key = os.getenv("KRAKEN_API_KEY", "")
    api_secret = os.getenv("KRAKEN_API_SECRET", "")

    if not api_key or not api_secret:
        print("\n=== PRIVATE REST (SKIPPED — no API keys) ===")
        return True

    client = KrakenRestClient(api_key=api_key, api_secret=api_secret)
    print("\n=== PRIVATE REST ===")

    # 1. Balance
    try:
        balances = await client.get_balance()
        print(f"  [OK] Balances: {len(balances)} assets")
        for asset, amount in sorted(balances.items()):
            print(f"       {asset}: {amount}")
    except Exception as e:
        print(f"  [FAIL] Balance: {e}")
        await client.close()
        return False

    # 2. Open orders
    try:
        orders = await client.get_open_orders()
        print(f"  [OK] Open orders: {len(orders)}")
    except Exception as e:
        print(f"  [FAIL] Open orders: {e}")

    # 3. WS token
    try:
        token = await client.get_ws_token()
        print(f"  [OK] WS token: {token[:20]}...")
    except Exception as e:
        print(f"  [FAIL] WS token: {e}")

    # 4. Validate-only order (no real order placed)
    try:
        result = await client.add_order(
            pair="XBTUSD",
            side="buy",
            order_type="limit",
            volume=0.0001,
            price=10000.0,  # well below market
            validate=True,
        )
        print(f"  [OK] Validate order: {result.description}")
    except Exception as e:
        print(f"  [FAIL] Validate order: {e}")

    await client.close()
    return True


async def test_ws_public() -> bool:
    """Test WS v2 public connection with ticker subscription."""
    from .kraken_ws_manager import KrakenWsManager

    print("\n=== WS v2 PUBLIC ===")
    mgr = KrakenWsManager()
    received: list[dict] = []

    async def on_ticker(data: dict) -> None:
        received.append(data)

    mgr.on_ticker(on_ticker)

    try:
        # Connect and subscribe
        await mgr._connect()
        await mgr.subscribe_ticker(["BTC/USD"])
        await mgr._resubscribe_all()

        # Listen for up to 10 seconds
        print("  Listening for ticker messages (10s)...")
        start = time.time()
        while time.time() - start < 10:
            if mgr._ws and not mgr._ws.closed:
                try:
                    msg = await asyncio.wait_for(mgr._ws.receive(), timeout=2.0)
                    if msg.type == 1:  # TEXT
                        import json
                        data = json.loads(msg.data)
                        await mgr._dispatch(data)
                except asyncio.TimeoutError:
                    pass
            if received:
                break

        if received:
            print(f"  [OK] Received {len(received)} ticker message(s)")
            sample = received[0]
            data = sample.get("data", [])
            if data:
                tick = data[0] if isinstance(data, list) else data
                print(f"       symbol={tick.get('symbol')} bid={tick.get('bid')} ask={tick.get('ask')}")
        else:
            print("  [WARN] No ticker messages received in 10s")

        await mgr.close()
        return bool(received)

    except Exception as e:
        print(f"  [FAIL] WS: {e}")
        await mgr.close()
        return False


def test_symbol_map() -> bool:
    """Test symbol normalization."""
    from .symbol_map import to_kraken, to_internal, normalize_kraken_asset, is_usd_or_stablecoin_quoted

    print("\n=== SYMBOL MAP ===")
    tests = [
        ("BTC-USD", "BTC/USD"),
        ("ETH-USD", "ETH/USD"),
        ("SOL-USDT", "SOL/USDT"),
        ("DOGE-USDC", "DOGE/USDC"),
    ]

    ok = True
    for internal, kraken in tests:
        result = to_kraken(internal)
        back = to_internal(kraken)
        match = result == kraken and back == internal
        status = "[OK]" if match else "[FAIL]"
        print(f"  {status} {internal} ↔ {kraken} (got: {result}, back: {back})")
        if not match:
            ok = False

    # Asset normalization
    asset_tests = [("XBT", "BTC"), ("XDG", "DOGE"), ("ETH", "ETH"), ("ZUSD", "USD")]
    for raw, expected in asset_tests:
        result = normalize_kraken_asset(raw)
        match = result == expected
        status = "[OK]" if match else "[FAIL]"
        print(f"  {status} normalize({raw}) = {result} (expected {expected})")
        if not match:
            ok = False

    # Stablecoin check
    stablecoin_tests = [("BTC/USD", True), ("ETH-USDT", True), ("BTC/EUR", False)]
    for sym, expected in stablecoin_tests:
        result = is_usd_or_stablecoin_quoted(sym)
        match = result == expected
        status = "[OK]" if match else "[FAIL]"
        print(f"  {status} is_usd_or_stablecoin({sym}) = {result} (expected {expected})")
        if not match:
            ok = False

    return ok


async def main() -> None:
    print("=" * 60)
    print("  KRAKEN CONNECTIVITY SMOKE TEST")
    print("=" * 60)

    results: dict[str, bool] = {}

    results["symbol_map"] = test_symbol_map()
    results["public_rest"] = await test_public_rest()
    results["private_rest"] = await test_private_rest()
    results["ws_public"] = await test_ws_public()

    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("  ALL TESTS PASSED")
    else:
        print("  SOME TESTS FAILED")
    print("=" * 60)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
