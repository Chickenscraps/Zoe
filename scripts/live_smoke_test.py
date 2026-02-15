"""
Live Smoke Test — $10 round-trip (sell BTC → buy BTC) to verify full pipeline.

This is a ONE-SHOT script (not a daemon). It:
1. Inits exchange + WS + local store + FIFO
2. Connects private WS, registers fill callback
3. Sells ~$10 of BTC-USD (market) → waits for fill via WS (30s timeout)
4. Verifies: fill in local_fills, FIFO realized P&L computed
5. Buys ~$10 of BTC-USD (market) → waits for fill via WS
6. Verifies: fill in local_fills, FIFO has new open lot
7. Prints summary: 2 fills, fees paid, net P&L

Since the account is ~100% BTC (~$149), we sell first then buy back.

Usage:
    python scripts/live_smoke_test.py

Requirements:
    - KRAKEN_API_KEY and KRAKEN_API_SECRET environment variables set
    - Account has at least $15 worth of BTC
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env.secrets"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("smoke_test")

# Test parameters
TEST_NOTIONAL_USD = 10.0      # $10 per leg
FILL_TIMEOUT_SEC = 30.0       # Max wait for fill via WS
SYMBOL = "BTC-USD"
WS_PAIR = "BTC/USD"           # Kraken WS v2 format
MODE = "live"

# ── WS event tracking ──
# Only track "update" events (not "snapshot" which includes old fills)
_ws_snapshot_done = False
_received_fills: list[dict[str, Any]] = []
_fill_event: asyncio.Event = asyncio.Event()


def _on_execution_event(data: dict[str, Any]) -> None:
    """WS execution callback — captures NEW fills only (ignores snapshot)."""
    global _ws_snapshot_done

    msg_type = data.get("type", "")

    if msg_type == "snapshot":
        # Mark snapshot as received — subsequent events are live
        snapshot_items = data.get("data", [])
        _ws_snapshot_done = True
        logger.info("  WS: received execution snapshot (%d historical items, ignoring)", len(snapshot_items))
        return

    # Only process "update" events (live fills)
    if msg_type != "update":
        return

    for item in data.get("data", []):
        exec_type = item.get("exec_type", "")
        if exec_type == "trade":
            _received_fills.append(item)
            _fill_event.set()
            logger.info(
                "  WS FILL: %s %s %.8f @ $%s (fee: $%s) order=%s",
                item.get("side", "?").upper(),
                item.get("symbol", "?"),
                float(item.get("last_qty", 0)),
                item.get("last_price", "?"),
                item.get("fee_paid", "0"),
                item.get("order_id", "?")[:12],
            )
        elif exec_type in ("filled", "new", "canceled"):
            logger.info(
                "  WS STATUS: order=%s status=%s",
                item.get("order_id", "?")[:12],
                item.get("order_status", item.get("exec_type", "?")),
            )


def get_fills_for_order(order_id: str) -> list[dict[str, Any]]:
    """Get all WS fills matching an order_id."""
    return [f for f in _received_fills if f.get("order_id") == order_id]


async def wait_for_order_fills(
    order_id: str,
    expected_qty: float,
    timeout: float = FILL_TIMEOUT_SEC,
) -> list[dict[str, Any]]:
    """Wait until WS fills for order_id sum to expected_qty (or timeout)."""
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        fills = get_fills_for_order(order_id)
        total_filled = sum(float(f.get("last_qty", 0)) for f in fills)

        if total_filled >= expected_qty * 0.99:  # 1% tolerance for rounding
            return fills

        # Wait for next fill event
        _fill_event.clear()
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            break
        try:
            await asyncio.wait_for(_fill_event.wait(), timeout=min(remaining, 3.0))
        except asyncio.TimeoutError:
            pass

    # Return whatever we have
    return get_fills_for_order(order_id)


def aggregate_fills(fills: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate multiple partial fills into a single summary."""
    if not fills:
        return {"qty": 0, "price": 0, "fee": 0, "cost": 0, "fill_ids": []}

    total_qty = 0.0
    total_cost = 0.0
    total_fee = 0.0
    fill_ids = []

    for f in fills:
        qty = float(f.get("last_qty") or f.get("qty", 0))
        price = float(f.get("last_price") or f.get("price", 0))
        fee = float(f.get("fee_paid") or f.get("fee", 0))
        total_qty += qty
        total_cost += qty * price
        total_fee += fee
        fill_ids.append(f.get("exec_id") or f.get("fill_id", ""))

    avg_price = total_cost / total_qty if total_qty > 0 else 0

    return {
        "qty": total_qty,
        "price": avg_price,
        "fee": total_fee,
        "cost": total_cost,
        "fill_ids": fill_ids,
        "fills": fills,
    }


async def run_smoke_test() -> bool:
    """Execute the full smoke test. Returns True on success."""
    from integrations.kraken_client.config import KrakenConfig
    from integrations.kraken_client.client import KrakenClient
    from integrations.kraken_client.ws import KrakenWebSocket
    from services.local_store import LocalEventStore
    from services.accounting.fifo_matcher import FIFOMatcher
    from services.crypto_trader.price_cache import PriceCache

    logger.info("=" * 60)
    logger.info("  ZOE LIVE SMOKE TEST — $%.0f Round Trip", TEST_NOTIONAL_USD)
    logger.info("=" * 60)

    # ── 1. Init exchange ──
    config = KrakenConfig.from_env()
    exchange = KrakenClient(config)
    ws = KrakenWebSocket(config)

    db_path = "data/smoke_test_live.db"
    store = LocalEventStore(db_path)
    fifo = FIFOMatcher()
    price_cache = PriceCache(store)

    success = False

    try:
        # ── 2. Pre-flight checks ──
        logger.info("\n--- Pre-flight checks ---")

        balances = await exchange.get_account_balances()
        usd_cash = 0.0
        for key in ("ZUSD", "USD", "USDT"):
            if key in balances:
                usd_cash = float(balances[key])
                break

        btc_balance = 0.0
        for key in ("XXBT", "XBT", "BTC"):
            if key in balances:
                btc_balance = float(balances[key])
                break

        # Get current BTC price
        ticker = await exchange.get_best_bid_ask(SYMBOL)
        results = ticker.get("results", [])
        if not results:
            logger.error("Cannot get BTC price!")
            return False

        btc_bid = float(results[0]["bid_price"])
        btc_ask = float(results[0]["ask_price"])
        btc_mid = (btc_bid + btc_ask) / 2
        btc_value = btc_balance * btc_mid
        total_value = usd_cash + btc_value

        logger.info("  BTC balance: %.8f (worth $%.2f)", btc_balance, btc_value)
        logger.info("  USD cash:    $%.2f", usd_cash)
        logger.info("  Total:       $%.2f", total_value)
        logger.info("  BTC price:   $%.2f (bid) / $%.2f (ask)", btc_bid, btc_ask)

        # Verify enough BTC to sell $10 worth
        sell_qty = TEST_NOTIONAL_USD / btc_bid  # conservative (sell at bid)
        if btc_balance < sell_qty * 1.05:  # 5% buffer
            logger.error(
                "Not enough BTC! Need ~%.8f to sell $%.0f, have %.8f",
                sell_qty, TEST_NOTIONAL_USD, btc_balance,
            )
            return False

        logger.info("  Sell qty needed: %.8f BTC ($%.2f)", sell_qty, TEST_NOTIONAL_USD)

        # ── 3. Connect WS ──
        logger.info("\n--- Connecting WebSocket ---")

        ws_token = await exchange.get_ws_token()
        ws.on_execution(_on_execution_event)
        await ws.connect_public()

        # Subscribe to BTC ticker for price cache
        from integrations.kraken_client.symbols import from_kraken

        def _on_ticker(data: dict[str, Any]) -> None:
            for item in data.get("data", []):
                raw_sym = item.get("symbol", "")
                bid = float(item.get("bid", 0))
                ask = float(item.get("ask", 0))
                if raw_sym and bid > 0 and ask > 0:
                    sym = from_kraken(raw_sym) if "/" in raw_sym else raw_sym
                    price_cache.update(sym, bid, ask)

        ws.on_ticker(_on_ticker)
        await ws.subscribe_ticker([WS_PAIR])

        await ws.connect_private(ws_token)
        logger.info("  WS connected (public + private)")

        # Wait for snapshot to arrive (so we can ignore it)
        logger.info("  Waiting for execution snapshot...")
        for _ in range(10):
            await asyncio.sleep(1)
            if _ws_snapshot_done:
                break
        if not _ws_snapshot_done:
            logger.warning("  Snapshot not received in 10s — proceeding anyway")

        # ── 4. LEG 1: Sell $10 BTC ──
        logger.info("\n--- LEG 1: SELL $%.0f BTC ---", TEST_NOTIONAL_USD)

        sell_resp = await exchange.place_order(
            symbol=SYMBOL,
            side="sell",
            order_type="market",
            qty=sell_qty,
            client_order_id=f"smokesell{int(time.time())}",
        )
        sell_order_id = sell_resp.get("id", "")
        logger.info("  Order submitted: %s", sell_order_id)

        if not sell_order_id:
            logger.error("  SELL order failed: %s", sell_resp)
            return False

        # Persist to local store
        store.insert_order({
            "id": sell_order_id,
            "client_order_id": sell_resp.get("client_order_id", ""),
            "symbol": SYMBOL,
            "side": "sell",
            "order_type": "market",
            "qty": sell_qty,
            "notional": TEST_NOTIONAL_USD,
            "status": "submitted",
            "mode": MODE,
            "raw_response": sell_resp,
        })

        # Wait for ALL fills via WS (market orders can split into multiple fills)
        logger.info("  Waiting for fills (max %ds)...", FILL_TIMEOUT_SEC)
        sell_fills = await wait_for_order_fills(sell_order_id, sell_qty)

        if not sell_fills:
            # Fallback: poll REST
            logger.warning("  WS fill timeout — polling REST...")
            await asyncio.sleep(2)  # Give time for order to settle
            rest_resp = await exchange.get_order_fills(sell_order_id)
            rest_fills = rest_resp.get("results", [])
            if rest_fills:
                sell_fills = rest_fills
                logger.info("  REST fallback found %d fills", len(rest_fills))
            else:
                order_state = await exchange.get_order(sell_order_id)
                logger.error("  No fills found! Order status: %s", order_state.get("status", "?"))
                return False

        sell_agg = aggregate_fills(sell_fills)
        logger.info(
            "  SELL FILLED: %.8f BTC @ avg $%.2f (fee: $%.4f, %d partial fills)",
            sell_agg["qty"], sell_agg["price"], sell_agg["fee"], len(sell_fills),
        )

        # Write each fill to local store and feed FIFO
        for i, fill in enumerate(sell_fills):
            fill_id = fill.get("exec_id") or fill.get("fill_id", f"sell-{sell_order_id}-{i}")
            qty = float(fill.get("last_qty") or fill.get("qty", 0))
            price = float(fill.get("last_price") or fill.get("price", 0))
            fee = float(fill.get("fee_paid") or fill.get("fee", 0))

            store.upsert_fill({
                "fill_id": fill_id,
                "order_id": sell_order_id,
                "symbol": SYMBOL,
                "side": "sell",
                "qty": qty,
                "price": price,
                "fee": fee,
                "fee_currency": "USD",
                "cost": qty * price,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "mode": MODE,
            })

            fifo.process_fill(
                symbol=SYMBOL, side="sell", qty=qty, price=price,
                fee=fee, fill_id=fill_id,
            )

        # Brief pause between legs — let balance settle on Kraken side
        logger.info("  Waiting 3s for balance to settle...")
        await asyncio.sleep(3)

        # ── 5. LEG 2: Buy $10 BTC ──
        logger.info("\n--- LEG 2: BUY $%.0f BTC ---", TEST_NOTIONAL_USD)

        # Check actual USD balance from sell proceeds
        balances2 = await exchange.get_account_balances()
        available_usd = 0.0
        for key in ("ZUSD", "USD", "USDT"):
            if key in balances2:
                available_usd = float(balances2[key])
                break

        logger.info("  Available USD after sell: $%.4f", available_usd)

        # Buy with 95% of available USD (leave room for fees)
        buy_notional = min(TEST_NOTIONAL_USD, available_usd * 0.95)
        if buy_notional < 1.0:
            logger.error("  Not enough USD to buy! Available: $%.4f", available_usd)
            return False

        # Get fresh price for buy qty
        ticker2 = await exchange.get_best_bid_ask(SYMBOL)
        results2 = ticker2.get("results", [])
        buy_ask = float(results2[0]["ask_price"]) if results2 else btc_ask
        buy_qty = buy_notional / buy_ask

        logger.info("  Buy qty: %.8f BTC ($%.2f) at ask $%.2f", buy_qty, buy_notional, buy_ask)

        buy_resp = await exchange.place_order(
            symbol=SYMBOL,
            side="buy",
            order_type="market",
            qty=buy_qty,
            client_order_id=f"smokebuy{int(time.time())}",
        )
        buy_order_id = buy_resp.get("id", "")
        logger.info("  Order submitted: %s", buy_order_id)

        if not buy_order_id:
            logger.error("  BUY order failed: %s", buy_resp)
            return False

        store.insert_order({
            "id": buy_order_id,
            "client_order_id": buy_resp.get("client_order_id", ""),
            "symbol": SYMBOL,
            "side": "buy",
            "order_type": "market",
            "qty": buy_qty,
            "notional": buy_notional,
            "status": "submitted",
            "mode": MODE,
            "raw_response": buy_resp,
        })

        # Wait for ALL fills
        logger.info("  Waiting for fills (max %ds)...", FILL_TIMEOUT_SEC)
        buy_fills = await wait_for_order_fills(buy_order_id, buy_qty)

        if not buy_fills:
            logger.warning("  WS fill timeout — polling REST...")
            await asyncio.sleep(2)
            rest_resp = await exchange.get_order_fills(buy_order_id)
            rest_fills = rest_resp.get("results", [])
            if rest_fills:
                buy_fills = rest_fills
                logger.info("  REST fallback found %d fills", len(rest_fills))
            else:
                order_state = await exchange.get_order(buy_order_id)
                logger.error("  No fills found! Order status: %s", order_state.get("status", "?"))
                return False

        buy_agg = aggregate_fills(buy_fills)
        logger.info(
            "  BUY FILLED: %.8f BTC @ avg $%.2f (fee: $%.4f, %d partial fills)",
            buy_agg["qty"], buy_agg["price"], buy_agg["fee"], len(buy_fills),
        )

        # Write each buy fill to local store and feed FIFO
        for i, fill in enumerate(buy_fills):
            fill_id = fill.get("exec_id") or fill.get("fill_id", f"buy-{buy_order_id}-{i}")
            qty = float(fill.get("last_qty") or fill.get("qty", 0))
            price = float(fill.get("last_price") or fill.get("price", 0))
            fee = float(fill.get("fee_paid") or fill.get("fee", 0))

            store.upsert_fill({
                "fill_id": fill_id,
                "order_id": buy_order_id,
                "symbol": SYMBOL,
                "side": "buy",
                "qty": qty,
                "price": price,
                "fee": fee,
                "fee_currency": "USD",
                "cost": qty * price,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "mode": MODE,
            })

            fifo.process_fill(
                symbol=SYMBOL, side="buy", qty=qty, price=price,
                fee=fee, fill_id=fill_id,
            )

        # ── 6. Summary ──
        logger.info("\n" + "=" * 60)
        logger.info("  SMOKE TEST RESULTS")
        logger.info("=" * 60)

        total_fees = sell_agg["fee"] + buy_agg["fee"]
        net_pnl = sell_agg["cost"] - buy_agg["cost"] - total_fees

        logger.info("  Leg 1 (SELL): %.8f BTC @ avg $%.2f = $%.4f (%d fills)",
                     sell_agg["qty"], sell_agg["price"], sell_agg["cost"], len(sell_fills))
        logger.info("  Leg 2 (BUY):  %.8f BTC @ avg $%.2f = $%.4f (%d fills)",
                     buy_agg["qty"], buy_agg["price"], buy_agg["cost"], len(buy_fills))
        logger.info("  Total fees:   $%.4f", total_fees)
        logger.info("  Net P&L:      $%.4f (spread + fees)", net_pnl)
        logger.info("  FIFO P&L:     $%.4f (realized)", fifo.get_realized_pnl())

        # ── 7. Verify local store ──
        logger.info("\n--- Verification ---")
        fills_in_db = store.get_all_fills(MODE)
        total_expected_fills = len(sell_fills) + len(buy_fills)
        logger.info("  Local fills count: %d (expected: %d)", len(fills_in_db), total_expected_fills)

        fifo_symbols = fifo.get_all_symbols()
        logger.info("  FIFO symbols: %s", fifo_symbols)

        for sym in fifo_symbols:
            lots = fifo.get_open_lots(sym)
            logger.info("  Open lots for %s: %d", sym, len(lots))
            for lot in lots:
                logger.info("    %.8f @ $%.2f (fee: $%.4f)", lot.qty, lot.price, lot.fee)

        logger.info("\n  Total WS fills received: %d", len(_received_fills))

        if len(fills_in_db) >= 2:
            logger.info("\n  SMOKE TEST PASSED!")
            success = True
        else:
            logger.error("\n  SMOKE TEST FAILED — expected >= 2 fills, got %d", len(fills_in_db))
            success = False

    except Exception as e:
        logger.error("Smoke test error: %s", e, exc_info=True)
        success = False

    finally:
        # Cleanup
        try:
            await ws.close()
        except Exception:
            pass
        try:
            await exchange.close()
        except Exception:
            pass

    return success


if __name__ == "__main__":
    result = asyncio.run(run_smoke_test())
    sys.exit(0 if result else 1)
