# Operations Runbook — Kraken Trading System

## Quick Start

### Environment Variables (Required)
```bash
# Kraken API (REQUIRED for live trading)
KRAKEN_API_KEY=          # From Kraken account → Security → API
KRAKEN_API_SECRET=       # Base64-encoded private key from Kraken

# Exchange selection
EXCHANGE=kraken          # "kraken" | "robinhood"

# Supabase (REQUIRED)
SUPABASE_URL=            # Project URL
SUPABASE_SERVICE_ROLE_KEY=  # Service role key (backend)
SUPABASE_KEY=            # Anon key (dashboard)

# Edge Factory
EDGE_FACTORY_MODE=paper  # "disabled" | "paper" | "live"
EDGE_FACTORY_SYMBOLS=BTC-USD,ETH-USD,SOL-USD

# Risk limits
MAX_NOTIONAL_PER_TRADE=25
MAX_DAILY_NOTIONAL=150
MAX_OPEN_POSITIONS=5
```

### Starting Services
```bash
# Market data WebSocket service
python -m services.market_data_ws

# Edge Factory trading engine
python -m services.edge_factory.runner

# Dashboard (development)
cd zoe-terminal && pnpm dev
```

## Kraken API Tier Limits

| Tier | Max API Calls | Decay Rate | Orders/min |
|------|--------------|------------|-----------|
| Starter | 15 | 1/3s | 60 |
| Intermediate | 20 | 1/2s | 125 |
| Pro | 20 | 1/1s | 225 |

Current tier: **Starter** (upgrade at Kraken → Settings → Account → Verification)

To upgrade: Complete Intermediate verification (gov ID + proof of residence). Pros: 2x API rate, 2x order rate, higher withdrawal limits.

## Incident Recovery

### Trading Engine Not Responding
1. Check `health_heartbeat` table for last heartbeat timestamp
2. If stale > 5 min: restart the service
3. Check Kraken system status: `GET https://api.kraken.com/0/public/SystemStatus`

### Reconciliation Mismatch
1. Check `crypto_reconciliation_events` for latest status
2. Compare Kraken balance (REST) vs DB positions
3. If mismatch: system enters DEGRADED mode automatically
4. To resume: fix mismatch manually, then set `STOP_TRADING_ON_DEGRADED=false` temporarily

### WebSocket Disconnection
1. Auto-reconnect with exponential backoff built in
2. If repeated failures: check Kraken system status
3. Check firewall / network configuration
4. Market data will be stale → safe mode activates → no new entries

## Secret Management
- Credentials in `.env` (gitignored) or environment variables
- NEVER commit `.env`, `kraken.txt`, or any file containing API keys
- Masked proof format: `KEY=****ABCD` (last 4 chars only)
- Rotate keys at Kraken → Security → API if compromised
