from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .config import EdgeFactoryConfig
from .features.base import BaseFeature
from .ingestion.base import BaseIngestor
from .models import FeatureSnapshot
from .repository import FeatureRepository

logger = logging.getLogger(__name__)


class FeatureEngine:
    """
    Orchestrates data ingestion and feature computation for all symbols.

    Flow:
    1. Call each ingestor to fetch raw data
    2. For each symbol, compute all registered features
    3. Store results in FeatureRepository
    4. Return feature snapshots for strategy consumption
    """

    def __init__(
        self,
        config: EdgeFactoryConfig,
        repository: FeatureRepository,
        ingestors: dict[str, BaseIngestor],  # {source_name: ingestor}
        features: list[BaseFeature],
    ):
        self.config = config
        self.repo = repository
        self.ingestors = ingestors
        self.features = features
        self.last_prices: dict[str, float] = {}  # {symbol: current_price}

    async def compute_all(
        self,
        symbols: list[str],
        extra_data: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Run full pipeline: ingest -> compute -> store.

        Args:
            symbols: List of symbols to process (e.g. ["BTC-USD", "ETH-USD"])
            extra_data: Additional data to merge per symbol (e.g. risk/account data)

        Returns:
            {symbol: {feature_name: value}} for all successfully computed features.
        """
        # Step 1: Ingest raw data from all sources
        raw_by_source: dict[str, dict[str, dict[str, Any]]] = {}
        for source_name, ingestor in self.ingestors.items():
            try:
                data = await ingestor.fetch(symbols)
                raw_by_source[source_name] = data
                logger.debug("Ingested %d symbols from %s", len(data), source_name)
            except Exception as e:
                logger.warning("Ingestor %s failed: %s", source_name, e)
                raw_by_source[source_name] = {}

        # Step 2: Compute features for each symbol
        results: dict[str, dict[str, float]] = {}
        now = datetime.now(timezone.utc)

        for symbol in symbols:
            symbol_features: dict[str, float] = {}

            # Merge all source data for this symbol
            merged_raw: dict[str, Any] = {}
            for source_name, source_data in raw_by_source.items():
                if symbol in source_data:
                    merged_raw.update(source_data[symbol])

            # Merge extra data (risk metrics, account state)
            if extra_data and symbol in extra_data:
                merged_raw.update(extra_data[symbol])
            elif extra_data and "_global" in extra_data:
                merged_raw.update(extra_data["_global"])

            # Cache current price for executor use
            cp = merged_raw.get("current_price", 0)
            if cp and cp > 0:
                self.last_prices[symbol] = float(cp)

            # Compute each feature
            for feature in self.features:
                try:
                    # Get feature history if needed
                    history = self.repo.get_feature_history(
                        symbol, feature.name, limit=30
                    )

                    value = feature.compute(merged_raw, history=history)
                    if value is not None:
                        symbol_features[feature.name] = value

                        # Store in repository
                        snapshot = FeatureSnapshot(
                            symbol=symbol,
                            feature_name=feature.name,
                            value=value,
                            computed_at=now,
                            source=feature.source,
                        )
                        self.repo.insert_feature(snapshot)

                except Exception as e:
                    logger.warning(
                        "Feature %s failed for %s: %s",
                        feature.name, symbol, e,
                    )

            results[symbol] = symbol_features
            logger.debug(
                "Computed %d features for %s", len(symbol_features), symbol
            )

        return results

    def get_latest_features(self, symbol: str) -> dict[str, float]:
        """Get the most recent feature values for a symbol from the repository."""
        result: dict[str, float] = {}
        for feature in self.features:
            snapshot = self.repo.get_latest_feature(symbol, feature.name)
            if snapshot is not None:
                result[feature.name] = snapshot.value
        return result

    def check_staleness(self, symbol: str) -> dict[str, bool]:
        """Check which features have stale data for a symbol."""
        now = datetime.now(timezone.utc)
        stale: dict[str, bool] = {}
        for source_name, ingestor in self.ingestors.items():
            latest = None
            for feature in self.features:
                if feature.source == source_name:
                    snap = self.repo.get_latest_feature(symbol, feature.name)
                    if snap and (latest is None or snap.computed_at > latest):
                        latest = snap.computed_at
            stale[source_name] = ingestor.is_stale(latest, now)
        return stale
