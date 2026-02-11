from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BaseIngestor(ABC):
    """Abstract base for all data ingestors."""

    @abstractmethod
    async def fetch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch raw data for symbols. Returns {symbol: {field: value}}."""
        ...

    @abstractmethod
    def staleness_threshold(self) -> int:
        """Seconds after which data is considered stale."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for this data source."""
        ...

    def is_stale(self, last_fetch: datetime | None, now: datetime) -> bool:
        """Check if data needs refreshing."""
        if last_fetch is None:
            return True
        elapsed = (now - last_fetch).total_seconds()
        return elapsed > self.staleness_threshold()
