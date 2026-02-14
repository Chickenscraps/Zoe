"""Broker factory — creates the correct Broker implementation based on config.

Usage:
    from .broker_factory import create_broker
    broker = await create_broker(config, repo=repo, market_data_provider=mdp)
"""

from __future__ import annotations

from typing import Any

from .broker import Broker, PaperBroker, RobinhoodBroker


async def create_broker(
    config: Any,
    *,
    repo: Any = None,
    market_data_provider: Any = None,
) -> Broker:
    """Create a Broker instance based on BROKER_TYPE config.

    Args:
        config: CryptoTraderConfig (must have .broker_type attribute)
        repo: Supabase repository (needed for PaperBroker)
        market_data_provider: Price data source (needed for PaperBroker)

    Returns:
        Configured Broker instance.

    Supported broker_type values:
        "paper"     — PaperBroker with simulated Kraken fees
        "robinhood" — RobinhoodBroker (legacy, requires RH client)
        "kraken"    — KrakenBroker (requires Kraken API key/secret)
    """
    broker_type = getattr(config, "broker_type", "paper").lower()

    if broker_type == "paper":
        if market_data_provider is None or repo is None:
            raise ValueError("PaperBroker requires market_data_provider and repo")
        starting_cash = getattr(config, "starting_equity", 2000.0)
        return PaperBroker(market_data_provider, repo, starting_cash=starting_cash)

    if broker_type == "robinhood":
        from integrations.robinhood_crypto_client import RobinhoodCryptoClient
        client = RobinhoodCryptoClient(
            api_key=config.rh_crypto_api_key,
            private_key_seed=config.rh_crypto_private_key_seed,
            base_url=getattr(config, "rh_crypto_base_url", "https://trading.robinhood.com"),
        )
        return RobinhoodBroker(client)

    if broker_type == "kraken":
        from .kraken_client import KrakenRestClient
        from .kraken_broker import KrakenBroker

        api_key = getattr(config, "kraken_api_key", "")
        api_secret = getattr(config, "kraken_api_secret", "")
        if not api_key or not api_secret:
            raise ValueError("KRAKEN_API_KEY and KRAKEN_API_SECRET are required for broker_type=kraken")

        base_url = getattr(config, "kraken_base_url", None)
        client = KrakenRestClient(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
        )
        broker = KrakenBroker(client)
        await broker.ensure_pair_cache()
        return broker

    raise ValueError(f"Unknown broker_type: {broker_type!r} (expected: paper, robinhood, kraken)")
