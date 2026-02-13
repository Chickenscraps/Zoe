from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Headers that must be redacted in any logging
REDACTED_HEADERS = {"api-key", "api-sign", "api-secret"}


@dataclass
class KrakenConfig:
    """Kraken API configuration loaded from environment variables."""

    api_key: str = ""
    api_secret: str = ""  # Base64-encoded private key
    base_url: str = "https://api.kraken.com"
    ws_public_url: str = "wss://ws.kraken.com/v2"
    ws_private_url: str = "wss://ws-auth.kraken.com/v2"
    timeout_seconds: int = 20
    max_retries: int = 3

    # Kraken rate limiting: Starter tier = 15 burst, +1 per 3s
    rate_limit_burst: int = field(default_factory=lambda: int(os.getenv("KRAKEN_RATE_BURST", "15")))
    rate_limit_decay_sec: float = field(default_factory=lambda: float(os.getenv("KRAKEN_RATE_DECAY", "3.0")))

    @classmethod
    def from_env(cls) -> KrakenConfig:
        """Load config from environment variables. Fails clearly if missing."""
        api_key = os.getenv("KRAKEN_API_KEY", "").strip()
        api_secret = os.getenv("KRAKEN_API_SECRET", "").strip()

        if not api_key:
            raise ValueError(
                "KRAKEN_API_KEY is not set. "
                "Set it in your .env file or as an environment variable."
            )
        if not api_secret:
            raise ValueError(
                "KRAKEN_API_SECRET is not set. "
                "Set it in your .env file or as an environment variable."
            )

        # Masked confirmation — never print full keys
        logger.info(
            "Kraken config loaded: KEY=****%s SECRET=****%s",
            api_key[-4:],
            api_secret[-4:],
        )

        return cls(
            api_key=api_key,
            api_secret=api_secret,
            base_url=os.getenv("KRAKEN_BASE_URL", "https://api.kraken.com"),
            ws_public_url=os.getenv("KRAKEN_WS_PUBLIC_URL", "wss://ws.kraken.com/v2"),
            ws_private_url=os.getenv("KRAKEN_WS_PRIVATE_URL", "wss://ws-auth.kraken.com/v2"),
            timeout_seconds=int(os.getenv("KRAKEN_TIMEOUT", "20")),
            max_retries=int(os.getenv("KRAKEN_MAX_RETRIES", "3")),
        )

    def masked_key(self) -> str:
        return f"****{self.api_key[-4:]}" if len(self.api_key) >= 4 else "****"

    def masked_secret(self) -> str:
        return f"****{self.api_secret[-4:]}" if len(self.api_secret) >= 4 else "****"
