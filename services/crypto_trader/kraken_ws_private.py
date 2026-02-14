"""Kraken authenticated WebSocket v2 client for private feeds.

Connects to wss://ws-auth.kraken.com/v2 with a token from REST
GetWebSocketsToken endpoint. Subscribes to:
  - executions: order status changes + trade fills
  - balances (optional): real-time balance updates

On each execution event, dispatches to registered callbacks.
Handles reconnection with token refresh.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine

import aiohttp

from .kraken_client import KrakenRestClient

logger = logging.getLogger(__name__)

MessageCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class KrakenWsPrivate:
    """Manages the authenticated Kraken WS v2 connection."""

    MAX_BACKOFF_S = 30.0
    TOKEN_REFRESH_MARGIN_S = 600  # refresh token 10 min before expected expiry

    def __init__(
        self,
        rest_client: KrakenRestClient,
        ws_auth_url: str = "wss://ws-auth.kraken.com/v2",
    ):
        self.rest = rest_client
        self.ws_auth_url = ws_auth_url
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._token: str = ""
        self._token_acquired_at: float = 0.0
        self._running = False
        self._last_message_time: float = 0.0
        self._reconnect_count: int = 0

        # Callbacks
        self._on_execution: list[MessageCallback] = []
        self._on_balance: list[MessageCallback] = []

    # ── Callback registration ──

    def on_execution(self, cb: MessageCallback) -> None:
        """Register callback for execution events (order fills, status changes)."""
        self._on_execution.append(cb)

    def on_balance(self, cb: MessageCallback) -> None:
        """Register callback for balance updates."""
        self._on_balance.append(cb)

    # ── Health ──

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    @property
    def last_message_age_s(self) -> float:
        if self._last_message_time == 0:
            return float("inf")
        return time.time() - self._last_message_time

    # ── Token management ──

    async def _ensure_token(self) -> str:
        """Get or refresh the WS authentication token."""
        now = time.time()
        # Token lasts ~15 min; refresh if > 10 min old
        if self._token and (now - self._token_acquired_at) < self.TOKEN_REFRESH_MARGIN_S:
            return self._token
        self._token = await self.rest.get_ws_token()
        self._token_acquired_at = now
        logger.info("WS auth token acquired/refreshed")
        return self._token

    # ── Connection lifecycle ──

    async def run(self) -> None:
        """Main loop: connect, authenticate, listen, reconnect on failure."""
        self._running = True
        backoff = 1.0

        while self._running:
            try:
                token = await self._ensure_token()
                await self._connect()
                await self._subscribe(token)
                backoff = 1.0
                await self._listen()
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                logger.warning("Private WS connection lost: %s. Reconnecting in %.1fs...", e, backoff)
            except Exception as e:
                logger.error("Private WS unexpected error: %s. Reconnecting in %.1fs...", e, backoff)
            finally:
                await self._close_ws()

            if self._running:
                self._reconnect_count += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.MAX_BACKOFF_S)

    async def stop(self) -> None:
        self._running = False
        await self._close_ws()

    async def _connect(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.ws_auth_url, heartbeat=10.0)
        self._last_message_time = time.time()
        logger.info("Private WS connected to %s", self.ws_auth_url)

    async def _close_ws(self) -> None:
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def _subscribe(self, token: str) -> None:
        """Subscribe to executions (and optionally balances) with auth token."""
        if not self._ws or self._ws.closed:
            return

        # Subscribe to executions (orders + fills)
        exec_msg = {
            "method": "subscribe",
            "params": {
                "channel": "executions",
                "token": token,
                "snap_orders": True,
                "snap_trades": True,
            },
        }
        await self._ws.send_json(exec_msg)
        logger.info("Private WS: subscribed to executions")

        # Subscribe to balances
        bal_msg = {
            "method": "subscribe",
            "params": {
                "channel": "balances",
                "token": token,
                "snap_orders": False,
            },
        }
        await self._ws.send_json(bal_msg)
        logger.info("Private WS: subscribed to balances")

    async def _listen(self) -> None:
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                self._last_message_time = time.time()
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                await self._dispatch(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("Private WS error: %s", self._ws.exception())
                break
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                logger.info("Private WS closed by server")
                break

    async def _dispatch(self, data: dict[str, Any]) -> None:
        channel = data.get("channel")
        msg_type = data.get("type")

        if channel == "heartbeat":
            return

        if msg_type in ("subscribe", "unsubscribe"):
            success = data.get("success", False)
            if not success:
                logger.error("Private WS subscription failed: %s", data)
            return

        if channel == "executions":
            for cb in self._on_execution:
                await cb(data)

        elif channel == "balances":
            for cb in self._on_balance:
                await cb(data)

    async def close(self) -> None:
        await self._close_ws()
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
