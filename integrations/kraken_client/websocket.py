"""Kraken WebSocket v2 client for live price + order updates.

Public WS (wss://ws.kraken.com/v2):
  - ticker channel for held asset pairs → updates price cache + candidate_scans

Private WS (wss://ws-auth.kraken.com/v2):
  - executions channel (fills) → upserts crypto_fills
  - balances channel → triggers reconciliation

Reconnection: exponential backoff (1s → 60s max), ping every 30s.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine

import aiohttp

from .client import KrakenClient, normalize_asset

log = logging.getLogger(__name__)

PUBLIC_WS_URL = "wss://ws.kraken.com/v2"
PRIVATE_WS_URL = "wss://ws-auth.kraken.com/v2"
PING_INTERVAL = 30  # seconds
MIN_RECONNECT_DELAY = 1.0
MAX_RECONNECT_DELAY = 60.0


class KrakenWebSocket:
    """Manages public + private WebSocket connections to Kraken v2 API."""

    def __init__(
        self,
        client: KrakenClient,
        on_ticker: Callable[[str, dict[str, Any]], Coroutine] | None = None,
        on_execution: Callable[[dict[str, Any]], Coroutine] | None = None,
        on_balance: Callable[[dict[str, Any]], Coroutine] | None = None,
    ):
        self.client = client
        self.on_ticker = on_ticker
        self.on_execution = on_execution
        self.on_balance = on_balance

        self._public_ws: aiohttp.ClientWebSocketResponse | None = None
        self._private_ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._subscribed_pairs: list[str] = []

    async def start(self, pairs: list[str] | None = None) -> None:
        """Start WebSocket connections.

        Args:
            pairs: Kraken pair names to subscribe for public ticker (e.g., ["XBT/USD", "ETH/USD"]).
                   If None, no public ticker subscription.
        """
        if self._running:
            return
        self._running = True
        self._subscribed_pairs = pairs or []
        self._session = aiohttp.ClientSession()

        if self._subscribed_pairs:
            self._tasks.append(asyncio.create_task(self._run_public()))
        if self.on_execution or self.on_balance:
            self._tasks.append(asyncio.create_task(self._run_private()))

        log.info("[KrakenWS] Started — public=%d pairs, private=%s",
                 len(self._subscribed_pairs),
                 "yes" if (self.on_execution or self.on_balance) else "no")

    async def stop(self) -> None:
        """Gracefully shut down all WebSocket connections."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        if self._public_ws and not self._public_ws.closed:
            await self._public_ws.close()
        if self._private_ws and not self._private_ws.closed:
            await self._private_ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        log.info("[KrakenWS] Stopped")

    # ------------------------------------------------------------------
    # Public WebSocket (ticker)
    # ------------------------------------------------------------------

    async def _run_public(self) -> None:
        """Connect and maintain the public WebSocket with reconnection."""
        delay = MIN_RECONNECT_DELAY
        while self._running:
            try:
                async with self._session.ws_connect(PUBLIC_WS_URL) as ws:  # type: ignore[union-attr]
                    self._public_ws = ws
                    delay = MIN_RECONNECT_DELAY
                    log.info("[KrakenWS] Public connected")

                    # Subscribe to ticker
                    await ws.send_json({
                        "method": "subscribe",
                        "params": {
                            "channel": "ticker",
                            "symbol": self._subscribed_pairs,
                        },
                    })

                    await self._read_loop(ws, self._handle_public_msg)

            except asyncio.CancelledError:
                return
            except Exception as e:
                log.warning("[KrakenWS] Public connection error: %s — reconnecting in %.0fs", e, delay)

            if not self._running:
                return
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_DELAY)

    async def _handle_public_msg(self, msg: dict[str, Any]) -> None:
        """Process a public WebSocket message."""
        channel = msg.get("channel")
        if channel == "ticker" and self.on_ticker:
            data = msg.get("data", [])
            for tick in data:
                symbol = tick.get("symbol", "")
                await self.on_ticker(symbol, tick)

    # ------------------------------------------------------------------
    # Private WebSocket (executions, balances)
    # ------------------------------------------------------------------

    async def _run_private(self) -> None:
        """Connect and maintain the private (auth) WebSocket with reconnection."""
        delay = MIN_RECONNECT_DELAY
        while self._running:
            try:
                # Get a fresh WS auth token
                token = await self.client.get_ws_token()
                if not token:
                    log.error("[KrakenWS] Failed to get WS auth token — retrying")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, MAX_RECONNECT_DELAY)
                    continue

                async with self._session.ws_connect(PRIVATE_WS_URL) as ws:  # type: ignore[union-attr]
                    self._private_ws = ws
                    delay = MIN_RECONNECT_DELAY
                    log.info("[KrakenWS] Private connected")

                    # Subscribe to executions (fills)
                    if self.on_execution:
                        await ws.send_json({
                            "method": "subscribe",
                            "params": {
                                "channel": "executions",
                                "token": token,
                                "snap_orders": False,
                                "snap_trades": False,
                            },
                        })

                    # Subscribe to balances
                    if self.on_balance:
                        await ws.send_json({
                            "method": "subscribe",
                            "params": {
                                "channel": "balances",
                                "token": token,
                                "snap_balances": True,
                            },
                        })

                    await self._read_loop(ws, self._handle_private_msg)

            except asyncio.CancelledError:
                return
            except Exception as e:
                log.warning("[KrakenWS] Private connection error: %s — reconnecting in %.0fs", e, delay)

            if not self._running:
                return
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_DELAY)

    async def _handle_private_msg(self, msg: dict[str, Any]) -> None:
        """Process a private WebSocket message."""
        channel = msg.get("channel")

        if channel == "executions" and self.on_execution:
            for trade in msg.get("data", []):
                await self.on_execution(trade)

        elif channel == "balances" and self.on_balance:
            await self.on_balance(msg.get("data", {}))

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    async def _read_loop(
        self,
        ws: aiohttp.ClientWebSocketResponse,
        handler: Callable[[dict[str, Any]], Coroutine],
    ) -> None:
        """Read messages from a WebSocket, handling pings and dispatching to handler."""
        last_ping = time.monotonic()

        async for raw in ws:
            if not self._running:
                return

            # Send periodic pings
            now = time.monotonic()
            if now - last_ping > PING_INTERVAL:
                await ws.send_json({"method": "ping"})
                last_ping = now

            if raw.type == aiohttp.WSMsgType.TEXT:
                try:
                    msg = json.loads(raw.data)
                except json.JSONDecodeError:
                    continue

                # Skip heartbeats and subscription confirmations
                method = msg.get("method")
                if method in ("pong", "heartbeat"):
                    continue
                if method == "subscribe" and msg.get("success"):
                    log.info("[KrakenWS] Subscribed: %s", msg.get("result", {}).get("channel"))
                    continue

                try:
                    await handler(msg)
                except Exception as e:
                    log.error("[KrakenWS] Handler error: %s", e, exc_info=True)

            elif raw.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break

    def update_pairs(self, pairs: list[str]) -> None:
        """Update the list of subscribed pairs (takes effect on next reconnect)."""
        self._subscribed_pairs = pairs

    @property
    def connected(self) -> bool:
        """True if at least one WebSocket is open."""
        pub = self._public_ws and not self._public_ws.closed
        priv = self._private_ws and not self._private_ws.closed
        return bool(pub or priv)
