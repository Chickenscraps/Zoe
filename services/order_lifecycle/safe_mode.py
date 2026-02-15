"""Safe mode — halts new entries when data is stale or API is degraded.

Checks:
1. Market data staleness: focus snapshot older than threshold → halt entries
2. API health: consecutive REST errors → halt entries, allow exits only
3. Publishes safe_mode status to health_heartbeat for dashboard alert
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class SafeModeConfig:
    """Configuration for safe mode checks."""

    def __init__(self) -> None:
        self.market_stale_sec = int(os.getenv("SAFE_MODE_MARKET_STALE_SEC", "60"))
        self.max_api_errors = int(os.getenv("SAFE_MODE_MAX_API_ERRORS", "3"))
        self.api_error_window_sec = int(os.getenv("SAFE_MODE_API_ERROR_WINDOW_SEC", "300"))


class SafeMode:
    """Monitors system health and determines if trading should be halted.

    When active:
    - New entries are blocked
    - Exits (sells) are still allowed
    - Dashboard shows safe_mode alert via health_heartbeat
    """

    def __init__(
        self,
        supabase_client: Any,
        config: SafeModeConfig | None = None,
    ):
        self._sb = supabase_client
        self.config = config or SafeModeConfig()
        self._api_errors: list[datetime] = []
        self._active = False
        self._reason = ""

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def reason(self) -> str:
        return self._reason

    def record_api_error(self, error: str = "") -> None:
        """Record an API error for health monitoring."""
        now = datetime.now(timezone.utc)
        self._api_errors.append(now)

        # Trim old errors outside window
        cutoff = now.timestamp() - self.config.api_error_window_sec
        self._api_errors = [
            e for e in self._api_errors if e.timestamp() > cutoff
        ]

        if len(self._api_errors) >= self.config.max_api_errors:
            self._activate(f"API degraded: {len(self._api_errors)} errors in {self.config.api_error_window_sec}s")

    def record_api_success(self) -> None:
        """Record a successful API call — may clear safe mode."""
        # Clear API errors on success
        self._api_errors.clear()
        if self._active and "API" in self._reason:
            self._deactivate("API recovered")

    async def check_market_data_health(self) -> bool:
        """Check if market data is fresh. Returns True if healthy."""
        try:
            resp = self._sb.table("market_snapshot_focus").select(
                "updated_at"
            ).order("updated_at", desc=True).limit(1).maybeSingle().execute()

            if not resp.data:
                self._activate("No market data available")
                return False

            updated = resp.data.get("updated_at", "")
            if not updated:
                self._activate("Market data timestamp missing")
                return False

            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()

            if age > self.config.market_stale_sec:
                self._activate(f"Market data stale ({age:.0f}s > {self.config.market_stale_sec}s)")
                return False

            # Data is fresh — clear market staleness if that was the reason
            if self._active and "Market data" in self._reason:
                self._deactivate("Market data recovered")

            return True

        except Exception as e:
            logger.warning("Market data health check failed: %s", e)
            return False

    def can_enter(self) -> bool:
        """Check if new entries are allowed. Blocked in safe mode."""
        return not self._active

    def can_exit(self) -> bool:
        """Exits are always allowed, even in safe mode."""
        return True

    def _activate(self, reason: str) -> None:
        """Enter safe mode."""
        if not self._active:
            logger.warning("SAFE MODE ACTIVATED: %s", reason)
        self._active = True
        self._reason = reason
        self._write_heartbeat()

    def _deactivate(self, reason: str) -> None:
        """Exit safe mode."""
        if self._active:
            logger.info("Safe mode deactivated: %s", reason)
        self._active = False
        self._reason = ""
        self._write_heartbeat()

    def _write_heartbeat(self) -> None:
        """Update health_heartbeat with safe mode status."""
        try:
            from datetime import datetime, timezone
            self._sb.table("health_heartbeat").upsert({
                "instance_id": "default",
                "component": "safe_mode",
                "status": "degraded" if self._active else "ok",
                "message": self._reason or "System healthy",
                "mode": "live",
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="instance_id,component,mode").execute()
        except Exception as e:
            logger.warning("Safe mode heartbeat write failed: %s", e)
