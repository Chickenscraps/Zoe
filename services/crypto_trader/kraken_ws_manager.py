"""Kraken WebSocket v2 connection manager.

Handles connection lifecycle for public WS (`wss://ws.kraken.com/v2`):
  - Connect, subscribe with snapshot, heartbeat monitoring
  - Auto-reconnect with exponential backoff
  - Resubscribe all channels on reconnect
  - Message dispatch to registered callbacks

Usage:
    mgr = KrakenWsManager(url="wss://ws.kraken.com/v2")
    mgr.on_ticker(callback)
    mgr.on_book(callback)
    mgr.on_trade(callback)
    await mgr.subscribe_ticker(["BTC/USD", "ETH/USD"])
    await mgr.run()  # blocks, reconnects on failure
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class WsSubscription:
    """Tracks an active subscription for replay on reconnect."""
    channel: str               # "ticker", "book", "trade"
    symbols: list[str]         # ["BTC/USD", "ETH/USD"]
    params: dict[str, Any] = field(default_factory=dict)  # depth, snapshot, etc.
    req_id: int = 0


MessageCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class KrakenWsManager:
    """Manages a single Kraken WS v2 public connection."""

    MAX_BACKOFF_S = 30.0
    HEARTBEAT_TIMEOUT_S = 15.0  # Kraken sends heartbeat every ~5s; stale after 15s

    def __init__(self, url: str = "wss://ws.kraken.com/v2"):
        self.url = url
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._subscriptions: list[WsSubscription] = []
        self._req_counter: int = 0
        self._running = False
        self._last_message_time: float = 0.0
        self._reconnect_count: int = 0

        # Callbacks per channel
        self._on_ticker: list[MessageCallback] = []
        self._on_book: list[MessageCallback] = []
        self._on_trade: list[MessageCallback] = []
        self._on_heartbeat: list[MessageCallback] = []
        self._on_status: list[MessageCallback] = []

    # ── Callback registration ──

    def on_ticker(self, cb: MessageCallback) -> None:
        self._on_ticker.append(cb)

    def on_book(self, cb: MessageCallback) -> None:
        self._on_book.append(cb)

    def on_trade(self, cb: MessageCallback) -> None:
        self._on_trade.append(cb)

    def on_heartbeat(self, cb: MessageCallback) -> None:
        self._on_heartbeat.append(cb)

    def on_status(self, cb: MessageCallback) -> None:
        self._on_status.append(cb)

    # ── Health ──

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    @property
    def last_message_age_s(self) -> float:
        if self._last_message_time == 0:
            return float("inf")
        return time.time() - self._last_message_time

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    # ── Subscribe helpers ──

    def _next_req_id(self) -> int:
        self._req_counter += 1
        return self._req_counter

    async def subscribe_ticker(self, symbols: list[str], event_trigger: str = "bbo") -> None:
        """Subscribe to ticker (Level-1 BBO) for given symbols."""
        sub = WsSubscription(
            channel="ticker",
            symbols=list(symbols),
            params={"event_trigger": event_trigger},
            req_id=self._next_req_id(),
        )
        self._subscriptions.append(sub)
        if self.connected:
            await self._send_subscribe(sub)

    async def subscribe_book(self, symbols: list[str], depth: int = 10) -> None:
        """Subscribe to book (Level-2 order book) for given symbols."""
        sub = WsSubscription(
            channel="book",
            symbols=list(symbols),
            params={"depth": depth, "snapshot": True},
            req_id=self._next_req_id(),
        )
        self._subscriptions.append(sub)
        if self.connected:
            await self._send_subscribe(sub)

    async def subscribe_trade(self, symbols: list[str], snapshot: bool = True) -> None:
        """Subscribe to individual trade events for given symbols."""
        sub = WsSubscription(
            channel="trade",
            symbols=list(symbols),
            params={"snapshot": snapshot},
            req_id=self._next_req_id(),
        )
        self._subscriptions.append(sub)
        if self.connected:
            await self._send_subscribe(sub)

    async def _send_subscribe(self, sub: WsSubscription) -> None:
        """Send a subscribe message over the WS connection."""
        if not self._ws or self._ws.closed:
            return
        msg: dict[str, Any] = {
            "method": "subscribe",
            "params": {
                "channel": sub.channel,
                "symbol": sub.symbols,
                **sub.params,
            },
        }
        if sub.req_id:
            msg["req_id"] = sub.req_id
        await self._ws.send_json(msg)
        logger.info("WS subscribe: channel=%s symbols=%s req_id=%d", sub.channel, sub.symbols, sub.req_id)

    async def _resubscribe_all(self) -> None:
        """Replay all subscriptions after reconnect."""
        for sub in self._subscriptions:
            sub.req_id = self._next_req_id()
            await self._send_subscribe(sub)

    # ── Connection lifecycle ──

    async def run(self) -> None:
        """Main loop: connect, listen, reconnect on failure. Blocks forever."""
        self._running = True
        backoff = 1.0

        while self._running:
            try:
                await self._connect()
                await self._resubscribe_all()
                backoff = 1.0  # reset on successful connect
                await self._listen()
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                logger.warning("WS connection lost: %s. Reconnecting in %.1fs...", e, backoff)
            except Exception as e:
                logger.error("WS unexpected error: %s. Reconnecting in %.1fs...", e, backoff)
            finally:
                await self._close_ws()

            if self._running:
                self._reconnect_count += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.MAX_BACKOFF_S)

    async def stop(self) -> None:
        """Gracefully stop the connection loop."""
        self._running = False
        await self._close_ws()

    async def _connect(self) -> None:
        """Open a new WS connection."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.url, heartbeat=10.0)
        self._last_message_time = time.time()
        logger.info("WS connected to %s", self.url)
        await self._dispatch_status({"event": "connected", "url": self.url})

    async def _close_ws(self) -> None:
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def _listen(self) -> None:
        """Read messages until connection drops."""
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                self._last_message_time = time.time()
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    logger.warning("WS invalid JSON: %s", msg.data[:200])
                    continue
                await self._dispatch(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("WS error: %s", self._ws.exception())
                break
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                logger.info("WS closed by server")
                break

    # ── Message dispatch ──

    async def _dispatch(self, data: dict[str, Any]) -> None:
        """Route incoming WS message to appropriate callbacks."""
        channel = data.get("channel")
        msg_type = data.get("type")

        if channel == "heartbeat":
            for cb in self._on_heartbeat:
                await cb(data)
            return

        if channel == "status":
            await self._dispatch_status(data)
            return

        if msg_type in ("subscribe", "unsubscribe"):
            # Subscription ack/error
            success = data.get("success", False)
            if not success:
                logger.error("WS subscription failed: %s", data)
            return

        # Data messages
        if channel == "ticker":
            for cb in self._on_ticker:
                await cb(data)
        elif channel == "book":
            for cb in self._on_book:
                await cb(data)
        elif channel == "trade":
            for cb in self._on_trade:
                await cb(data)

    async def _dispatch_status(self, data: dict[str, Any]) -> None:
        for cb in self._on_status:
            await cb(data)

    # ── Cleanup ──

    async def close(self) -> None:
        """Close connection and session."""
        await self._close_ws()
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
