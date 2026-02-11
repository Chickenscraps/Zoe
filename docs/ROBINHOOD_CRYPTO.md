# Robinhood Crypto Trading API Integration

Zoe integrates with Robinhood's official Crypto Trading API for **read-only** account and holdings visibility. Live trading is disabled by default.

## Key Generation (Ed25519)

Robinhood's API uses Ed25519 signatures. Generate a keypair:

```bash
# Generate a 32-byte Ed25519 seed and encode as base64
openssl genpkey -algorithm ed25519 -outform DER | tail -c 32 | base64
```

Or in Python:

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64

private_key = Ed25519PrivateKey.generate()
seed = private_key.private_bytes_raw()  # 32 bytes
print(base64.b64encode(seed).decode())
```

Register the **public key** with Robinhood via their developer portal. Keep the private seed secret.

## Required Environment Variables

Store these in `.env.secrets` (never commit this file):

```env
# Robinhood Crypto Trading API
RH_CRYPTO_API_KEY=your-api-key-here
RH_CRYPTO_PRIVATE_KEY_SEED=base64-encoded-32-byte-ed25519-seed
RH_CRYPTO_BASE_URL=https://trading.robinhood.com
RH_ALLOW_LIVE=false
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `RH_CRYPTO_API_KEY` | Yes | — | API key from Robinhood developer portal |
| `RH_CRYPTO_PRIVATE_KEY_SEED` | Yes | — | 32-byte Ed25519 seed, base64-encoded |
| `RH_CRYPTO_BASE_URL` | No | `https://trading.robinhood.com` | API base URL |
| `RH_ALLOW_LIVE` | No | `false` | Set to `true` to enable POST/DELETE (live trading) |

## Keeping Live Trading Disabled

**RH_ALLOW_LIVE defaults to `false`.**

When `false`, any POST, PUT, or DELETE request will immediately throw a `RhCryptoError` with code `LIVE_DISABLED`. This is enforced at the request helper level before any network call is made.

To run in read-only mode (recommended for Zoe paper trading):
- Do NOT set `RH_ALLOW_LIVE` at all, or set it to `false`
- Only GET endpoints will work (accounts, holdings, orders list, trading pairs, bid/ask)

## Health Check

Run the standalone health check:

```bash
npx tsx scripts/rh_crypto_healthcheck.ts
```

Output:
```
=== Robinhood Crypto API Health Check ===

PASS  | HTTP 200 | 142ms
      | Response keys: account_number, status, buying_power, ...
      | Result appended to logs/rh_crypto_health.log
```

If Supabase is configured (`VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`), results are also written to the `health_heartbeat` table.

The health check also appears in:
- **CLI**: `openclaw health` shows "Robinhood Crypto: ok (142ms)" or "Robinhood Crypto: failed - ..."
- **Dashboard**: Health page shows a "Robinhood Crypto Connector" card with live status

## Authentication / Signing Protocol

Every request is signed with Ed25519. The message format is:

```
message_to_sign = api_key + timestamp + api_path + http_method + request_body
```

Where:
- `api_key` — your RH_CRYPTO_API_KEY
- `timestamp` — Unix epoch seconds as a string
- `api_path` — path only, e.g. `/api/v1/crypto/trading/orders/`
- `http_method` — uppercase, e.g. `GET`, `POST`
- `request_body` — empty string for GET/DELETE, canonical JSON for POST/PUT

The signature is sent as three headers:
- `x-api-key` — the API key
- `x-timestamp` — the timestamp used in signing
- `x-signature` — base64-encoded Ed25519 signature

**Critical**: For POST/PUT, the JSON body must be serialized deterministically (sorted keys, no whitespace) and the **exact same string** must be used for both signing and the HTTP body.

## Common Failure Modes

### Signature Mismatch (HTTP 401)
- **Cause**: The message_to_sign on your end doesn't match what Robinhood expects
- **Fix**: Ensure you're using the exact path (with trailing slash), uppercase method, and canonical JSON body
- **Debug**: Enable logging to verify message_to_sign structure

### Timestamp Drift (HTTP 401)
- **Cause**: Server clock is out of sync with Robinhood's servers
- **Fix**: Ensure NTP is enabled. Robinhood typically allows ~30 seconds of drift
- **Debug**: Compare `x-timestamp` with actual UTC epoch seconds

### Rate Limiting (HTTP 429)
- **Cause**: Too many requests per second
- **Fix**: The client automatically retries with exponential backoff (500ms, 1s, 2s). Reduce polling frequency if persistent

### Wrong Key Format
- **Cause**: `RH_CRYPTO_PRIVATE_KEY_SEED` is not a valid base64-encoded 32-byte seed
- **Fix**: The seed must decode to exactly 32 bytes. Verify with: `echo "YOUR_SEED" | base64 -d | wc -c`

### Server Errors (HTTP 5xx)
- **Cause**: Robinhood API issues
- **Fix**: The client retries up to 3 times automatically. Check Robinhood's status page

## Available Endpoints

The client exposes these convenience functions (all GET, safe by default):

| Function | Endpoint | Description |
|---|---|---|
| `getAccount()` | `/api/v1/crypto/trading/accounts/` | Account info |
| `getHoldings()` | `/api/v1/crypto/trading/holdings/` | Current crypto holdings |
| `getOrders()` | `/api/v1/crypto/trading/orders/` | Order history |
| `getTradingPairs()` | `/api/v1/crypto/trading/trading_pairs/` | Available trading pairs |
| `getBestBidAsk(symbol)` | `/api/v1/crypto/trading/best_bid_ask/` | Real-time bid/ask |
| `getEstimatedPrice(...)` | `/api/v1/crypto/trading/estimated_price/` | Price estimate |

For custom endpoints, use `rhRequest(method, path, { body, query })` directly.

## Architecture Notes

- **Non-blocking**: The Robinhood connector never blocks Zoe's main trading loop. If it fails, Zoe continues operating normally
- **Not canonical for market data**: Polygon remains the canonical data source for options/equities. Robinhood Crypto is supplementary
- **Paper trading only**: Zoe is designed for paper trading. The `RH_ALLOW_LIVE=false` gate is an extra safety layer
