"""Heartbeat Monitor — Dead-man's switch for WebSocket connections.

Monitors WS heartbeats and triggers emergency actions if connection
is lost. Cancels all open orders if heartbeat is missed for too long.

Reference: "Kraken WebSocket API FAQ — heartbeat monitoring"
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatStatus:
    """Current heartbeat status for a connection."""
    name: str
    is_alive: bool = True
    last_heartbeat: float = 0.0
    missed_count: int = 0
    total_heartbeats: int = 0
    reconnect_count: int = 0
    last_reconnect: float = 0.0


class HeartbeatMonitor:
    """Monitors WebSocket heartbeats and triggers dead-man's switch.

    Usage:
        monitor = HeartbeatMonitor(
            timeout_seconds=5.0,
            on_timeout=cancel_all_orders,
            on_reconnect=reconnect_ws,
        )

        # In WS message handler:
        monitor.heartbeat("public_ws")

        # Start monitoring loop:
        await monitor.start()
    """

    def __init__(
        self,
        timeout_seconds: float = 5.0,
        max_missed_before_action: int = 3,
        check_interval: float = 1.0,
        on_timeout: Optional[Callable[..., Coroutine]] = None,
        on_reconnect: Optional[Callable[..., Coroutine]] = None,
    ):
        self.timeout = timeout_seconds
        self.max_missed = max_missed_before_action
        self.check_interval = check_interval
        self.on_timeout = on_timeout
        self.on_reconnect = on_reconnect

        self._connections: dict[str, HeartbeatStatus] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def register(self, name: str) -> None:
        """Register a connection to monitor."""
        self._connections[name] = HeartbeatStatus(
            name=name,
            last_heartbeat=time.time(),
        )
        logger.info("Heartbeat monitor: registered '%s'", name)

    def heartbeat(self, name: str) -> None:
        """Record a heartbeat from a connection."""
        status = self._connections.get(name)
        if status is None:
            self.register(name)
            status = self._connections[name]

        status.last_heartbeat = time.time()
        status.is_alive = True
        status.missed_count = 0
        status.total_heartbeats += 1

    def is_alive(self, name: str) -> bool:
        """Check if a specific connection is alive."""
        status = self._connections.get(name)
        if status is None:
            return False
        return status.is_alive

    def all_alive(self) -> bool:
        """Check if all connections are alive."""
        return all(s.is_alive for s in self._connections.values())

    async def start(self) -> None:
        """Start the heartbeat monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Heartbeat monitor started (timeout=%.1fs)", self.timeout)

    async def stop(self) -> None:
        """Stop the heartbeat monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._check_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat monitor error: %s", e)

    async def _safe_callback(
        self,
        callback: Callable[..., Coroutine],
        name: str,
        label: str,
    ) -> None:
        """Run a callback safely, catching and logging exceptions."""
        try:
            await callback(name)
        except Exception as e:
            logger.error(
                "Heartbeat %s handler failed for '%s': %s", label, name, e,
            )

    async def _check_all(self) -> None:
        """Check all registered connections."""
        now = time.time()

        for name, status in self._connections.items():
            elapsed = now - status.last_heartbeat

            if elapsed > self.timeout:
                status.missed_count += 1
                was_alive = status.is_alive

                if status.missed_count >= self.max_missed:
                    status.is_alive = False

                    if was_alive:
                        logger.warning(
                            "HEARTBEAT LOST: '%s' (missed %d, %.1fs since last)",
                            name, status.missed_count, elapsed,
                        )

                        # Trigger dead-man's switch (fire-and-forget to avoid blocking)
                        if self.on_timeout:
                            asyncio.create_task(
                                self._safe_callback(self.on_timeout, name, "timeout")
                            )

                        # Attempt reconnect (fire-and-forget)
                        if self.on_reconnect:
                            async def _do_reconnect(n: str = name, s: HeartbeatStatus = status, t: float = now) -> None:
                                try:
                                    logger.info("Attempting reconnect for '%s'...", n)
                                    await self.on_reconnect(n)
                                    s.reconnect_count += 1
                                    s.last_reconnect = t
                                except Exception as e:
                                    logger.error("Reconnect failed for '%s': %s", n, e)
                            asyncio.create_task(_do_reconnect())
                else:
                    logger.debug(
                        "Heartbeat delayed: '%s' (missed %d/%d)",
                        name, status.missed_count, self.max_missed,
                    )

    @property
    def summary(self) -> dict[str, Any]:
        """Current heartbeat monitor status."""
        now = time.time()
        return {
            name: {
                "alive": status.is_alive,
                "seconds_since_heartbeat": round(now - status.last_heartbeat, 1),
                "missed_count": status.missed_count,
                "total_heartbeats": status.total_heartbeats,
                "reconnect_count": status.reconnect_count,
            }
            for name, status in self._connections.items()
        }
