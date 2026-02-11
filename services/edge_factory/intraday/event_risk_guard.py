from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class EventRiskGuard:
    """
    Economic calendar gate: block entries T-30min to T+30min around events.

    Implementation: manual schedule config via env var (JSON list of ISO timestamps).
    Can be updated without code changes.

    Exits are always allowed during event windows.
    """

    def __init__(self, buffer_minutes: int = 30):
        self.buffer = timedelta(minutes=buffer_minutes)
        self._events = self._load_events()

    def _load_events(self) -> list[datetime]:
        """Load event schedule from env var."""
        raw = os.getenv("EF_INTRADAY_EVENT_SCHEDULE", "[]")
        try:
            timestamps = json.loads(raw)
            events = []
            for ts in timestamps:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    events.append(dt)
            return events
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse event schedule: %s", e)
            return []

    def is_high_impact_window(
        self, now: datetime | None = None
    ) -> tuple[bool, str]:
        """
        Check if we're in a high-impact event window.

        Returns (blocked: bool, reason: str).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        for event_time in self._events:
            window_start = event_time - self.buffer
            window_end = event_time + self.buffer

            if window_start <= now <= window_end:
                return True, "event at %s" % event_time.strftime("%Y-%m-%d %H:%M UTC")

        return False, ""

    def add_event(self, event_time: datetime) -> None:
        """Add an event to the schedule (runtime only, not persisted)."""
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        self._events.append(event_time)
        self._events.sort()

    def upcoming_events(self, now: datetime | None = None, limit: int = 5) -> list[datetime]:
        """Get next N upcoming events."""
        if now is None:
            now = datetime.now(timezone.utc)
        return [e for e in self._events if e > now][:limit]
