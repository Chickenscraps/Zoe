from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import FeatureSnapshot


class BaseFeature(ABC):
    """Abstract base for feature computation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique feature identifier (e.g. 'trend_z_score_14d')."""
        ...

    @property
    @abstractmethod
    def source(self) -> str:
        """Data source this feature reads from (e.g. 'google_trends')."""
        ...

    @abstractmethod
    def compute(
        self,
        raw_data: dict[str, Any],
        history: list[FeatureSnapshot] | None = None,
    ) -> float | None:
        """
        Compute feature value from raw ingested data.
        Returns None if insufficient data.

        Args:
            raw_data: Output from the corresponding ingestor.
            history: Previous feature values (for features that need their own history).
        """
        ...

    @property
    def required_sources(self) -> list[str]:
        """List of source names this feature needs. Defaults to [self.source]."""
        return [self.source]
