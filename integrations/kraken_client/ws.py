"""Kraken WebSocket v2 client for public and private data streams.

Public channels (wss://ws.kraken.com/v2):
  - ticker: real-time bid/ask/last/volume
  - book: order book updates
  - trade: recent trades

Private channels (wss://ws-auth.kraken.com/v2):
  - executions: order fills and status changes
  - (requires auth token from REST API)

Features:
  - Auto-reconnect with exponential backoff + jitter
  - Heartbeat handling (ping/pong)
  - Callback-based event dispatch
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Callable, Optional

import aiohttp

from .config import KrakenConfig

logger = logging.getLogger(__name__)

# Type alias for callbacks
Callback = Callable[[dict[str, Any]], None]


class KrakenWebSocket:
    """Manages Kraken WS v2 connections (public + private)."""

    def __init__(self, config: KrakenConfig):
        self._config = config
        self._public_ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._private_ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

        # Callbacks
        self._on_ticker: list[Callback] = []
        self._on_book: list[Callback] = []
        self._on_trade: list[Callback] = []
        self._on_execution: list[Callback] = []
        self._on_open_orders: list[Callback] = []

        # Reconnect state
        self._public_reconnect_attempts = 0
        self._private_reconnect_attempts = 0
        self._max_reconnect_delay = 60

        # Connection readiness events
        self._public_connected_event = asyncio.Event()
        self._private_connected_event = asyncio.Event()

        # Public subscriptions to restore on reconnect
        self._public_first_connect = True  # Skip resubscribe on first connect
        self._ticker_pairs: list[str] = []
        self._book_pairs: list[str] = []
        self._book_depth: int = 10
        self._trade_pairs: list[str] = []

        # Private auth token
        self._ws_token: Optional[str] = None

        # Background tasks
        self._tasks: list[asyncio.Task] = []

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # ── Callback Registration ──────────────────────────────────

    def on_ticker(self, callback: Callback) -> None:
        self._on_ticker.append(callback)

    def on_book(self, callback: Callback) -> None:
        self._on_book.append(callback)

    def on_trade(self, callback: Callback) -> None:
        self._on_trade.append(callback)

    def on_execution(self, callback: Callback) -> None:
        self._on_execution.append(callback)

    def on_open_orders(self, callback: Callback) -> None:
        self._on_open_orders.append(callback)

    # ── Public WebSocket ───────────────────────────────────────

    async def connect_public(self) -> None:
        """Connect to public WS and start message loop."""
        self._running = True
        task = asyncio.create_task(self._public_loop())
        self._tasks.append(task)

    async def _public_loop(self) -> None:
        """Main loop for public WS: connect, listen, reconnect on failure."""
        while self._running:
            try:
                session = await self._get_session()
                logger.info("Connecting to public WS: %s", self._config.ws_public_url)
                self._public_ws = await session.ws_connect(
                    self._config.ws_public_url,
                    heartbeat=30,
                )
                self._public_reconnect_attempts = 0
                logger.info("Public WS connected")
                self._public_connected_event.set()

                # Resubscribe to channels (skip on first connect — caller will subscribe)
                if self._public_first_connect:
                    self._public_first_connect = False
                else:
                    await self._resubscribe_public()

                # Message loop
                async for msg in self._public_ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self._handle_public_message(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error("Public WS error: %s", self._public_ws.exception())
                        break
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                        logger.warning("Public WS closed")
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Public WS connection error: %s", e)

            if not self._running:
                break

            # Reconnect with backoff
            self._public_reconnect_attempts += 1
            delay = min(
                2 ** self._public_reconnect_attempts + random.uniform(0, 1),
                self._max_reconnect_delay,
            )
            logger.info("Public WS reconnecting in %.1fs (attempt %d)", delay, self._public_reconnect_attempts)
            await asyncio.sleep(delay)

    async def _resubscribe_public(self) -> None:
        """Resubscribe to all public channels after reconnect."""
        if self._ticker_pairs:
            await self._send_public({
                "method": "subscribe",
                "params": {
                    "channel": "ticker",
                    "symbol": self._ticker_pairs,
                },
            })
        if self._book_pairs:
            await self._send_public({
                "method": "subscribe",
                "params": {
                    "channel": "book",
                    "symbol": self._book_pairs,
                    "depth": self._book_depth,
                },
            })
        if self._trade_pairs:
            await self._send_public({
                "method": "subscribe",
                "params": {
                    "channel": "trade",
                    "symbol": self._trade_pairs,
                },
            })

    def _handle_public_message(self, raw: str) -> None:
        """Parse and dispatch a public WS message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from public WS: %s", raw[:200])
            return

        # Kraken WS v2 message format:
        # {"channel": "ticker", "type": "update", "data": [...]}
        # {"channel": "heartbeat"}
        # {"method": "subscribe", "success": true, ...}

        channel = data.get("channel", "")

        if channel == "heartbeat":
            return  # Normal keepalive

        if channel == "ticker":
            for cb in self._on_ticker:
                try:
                    cb(data)
                except Exception as e:
                    logger.error("Ticker callback error: %s", e)

        elif channel == "book":
            for cb in self._on_book:
                try:
                    cb(data)
                except Exception as e:
                    logger.error("Book callback error: %s", e)

        elif channel == "trade":
            for cb in self._on_trade:
                try:
                    cb(data)
                except Exception as e:
                    logger.error("Trade callback error: %s", e)

        elif data.get("method") in ("subscribe", "unsubscribe"):
            success = data.get("success", False)
            result_info = data.get("result", {})
            channel = result_info.get("channel", "?") if isinstance(result_info, dict) else "?"
            if success:
                logger.info("WS %s success: %s", data["method"], channel)
            else:
                logger.error(
                    "WS %s FAILED: channel=%s error=%s",
                    data["method"],
                    channel,
                    data.get("error", "unknown"),
                )

    async def _send_public(self, payload: dict[str, Any]) -> None:
        if self._public_ws and not self._public_ws.closed:
            await self._public_ws.send_json(payload)

    # ── Public Subscriptions ───────────────────────────────────

    async def subscribe_ticker(self, pairs: list[str]) -> None:
        """Subscribe to ticker updates for given WS-format pairs (e.g. ["XBT/USD"])."""
        self._ticker_pairs = list(set(self._ticker_pairs + pairs))
        # Wait for connection if not yet ready
        await asyncio.wait_for(self._public_connected_event.wait(), timeout=10)
        await self._send_public({
            "method": "subscribe",
            "params": {
                "channel": "ticker",
                "symbol": pairs,
            },
        })

    async def unsubscribe_ticker(self, pairs: list[str]) -> None:
        """Unsubscribe from ticker updates."""
        self._ticker_pairs = [p for p in self._ticker_pairs if p not in pairs]
        if self._public_ws and not self._public_ws.closed:
            await self._send_public({
                "method": "unsubscribe",
                "params": {
                    "channel": "ticker",
                    "symbol": pairs,
                },
            })

    async def subscribe_book(self, pairs: list[str], depth: int = 10) -> None:
        """Subscribe to order book updates."""
        self._book_pairs = list(set(self._book_pairs + pairs))
        self._book_depth = depth
        await asyncio.wait_for(self._public_connected_event.wait(), timeout=10)
        await self._send_public({
            "method": "subscribe",
            "params": {
                "channel": "book",
                "symbol": pairs,
                "depth": depth,
            },
        })

    async def subscribe_trades(self, pairs: list[str]) -> None:
        """Subscribe to trade updates."""
        self._trade_pairs = list(set(self._trade_pairs + pairs))
        await asyncio.wait_for(self._public_connected_event.wait(), timeout=10)
        await self._send_public({
            "method": "subscribe",
            "params": {
                "channel": "trade",
                "symbol": pairs,
            },
        })

    # ── Private WebSocket ──────────────────────────────────────

    async def connect_private(self, ws_token: str) -> None:
        """Connect to private WS with auth token and start message loop."""
        self._ws_token = ws_token
        self._running = True
        task = asyncio.create_task(self._private_loop())
        self._tasks.append(task)

    async def _private_loop(self) -> None:
        """Main loop for private WS: connect, auth, listen, reconnect."""
        while self._running:
            if not self._ws_token:
                logger.error("No WS token for private connection")
                await asyncio.sleep(5)
                continue

            try:
                session = await self._get_session()
                logger.info("Connecting to private WS: %s", self._config.ws_private_url)
                self._private_ws = await session.ws_connect(
                    self._config.ws_private_url,
                    heartbeat=30,
                )
                self._private_reconnect_attempts = 0
                logger.info("Private WS connected")
                self._private_connected_event.set()

                # Subscribe to executions channel with token
                await self._send_private({
                    "method": "subscribe",
                    "params": {
                        "channel": "executions",
                        "token": self._ws_token,
                        "snap_orders": True,
                        "snap_trades": True,
                    },
                })

                # Message loop
                async for msg in self._private_ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self._handle_private_message(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error("Private WS error: %s", self._private_ws.exception())
                        break
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                        logger.warning("Private WS closed")
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Private WS connection error: %s", e)

            if not self._running:
                break

            # Reconnect with backoff
            self._private_reconnect_attempts += 1
            delay = min(
                2 ** self._private_reconnect_attempts + random.uniform(0, 1),
                self._max_reconnect_delay,
            )
            logger.info("Private WS reconnecting in %.1fs (attempt %d)", delay, self._private_reconnect_attempts)
            await asyncio.sleep(delay)

    def _handle_private_message(self, raw: str) -> None:
        """Parse and dispatch a private WS message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from private WS: %s", raw[:200])
            return

        channel = data.get("channel", "")

        if channel == "heartbeat":
            return

        if channel == "executions":
            msg_type = data.get("type", "")
            # "snapshot" = initial state, "update" = new events
            for cb in self._on_execution:
                try:
                    cb(data)
                except Exception as e:
                    logger.error("Execution callback error: %s", e)

        elif data.get("method") in ("subscribe", "unsubscribe"):
            success = data.get("success", False)
            logger.info(
                "Private WS %s %s: %s",
                data["method"],
                "success" if success else "FAILED",
                data.get("result", {}).get("channel", "?"),
            )
            if not success:
                logger.error("Private WS subscription failed: %s", data.get("error", "unknown"))

    async def _send_private(self, payload: dict[str, Any]) -> None:
        if self._private_ws and not self._private_ws.closed:
            await self._private_ws.send_json(payload)

    # ── Lifecycle ──────────────────────────────────────────────

    @property
    def public_connected(self) -> bool:
        return self._public_ws is not None and not self._public_ws.closed

    @property
    def private_connected(self) -> bool:
        return self._private_ws is not None and not self._private_ws.closed

    async def close(self) -> None:
        """Gracefully close all connections and cancel background tasks."""
        self._running = False

        for task in self._tasks:
            task.cancel()

        if self._public_ws and not self._public_ws.closed:
            await self._public_ws.close()
        if self._private_ws and not self._private_ws.closed:
            await self._private_ws.close()
        if self._session and not self._session.closed:
            await self._session.close()

        # Wait for tasks to finish
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()
        logger.info("Kraken WebSocket connections closed")
