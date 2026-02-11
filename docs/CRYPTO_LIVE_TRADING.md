# Crypto Live Trading (Robinhood)

This guide enables **crypto-only** live trading with Robinhood as the source of truth.

## Safety Defaults

- `RH_LIVE_TRADING=false` by default.
- Live execution requires all 3 gates:
  - `RH_LIVE_TRADING=true`
  - request initiator must match `ADMIN_USER_ID`
  - `RH_LIVE_CONFIRM="I UNDERSTAND THIS IS REAL MONEY"`
- Hard limits:
  - `MAX_NOTIONAL_PER_TRADE` (default `10`)
  - `MAX_DAILY_NOTIONAL` (default `50`)
  - `MAX_OPEN_POSITIONS` (default `3`)
- If reconciliation degrades and `STOP_TRADING_ON_DEGRADED=true`, order entry is frozen.
- Crypto symbol guard is enforced: only `*-USD` pairs are accepted (for example `BTC-USD`, `ETH-USD`).

## Environment

Copy from `.env.example` and fill secrets in local `.env.secrets` (gitignored):

- `RH_CRYPTO_API_KEY`
- `RH_CRYPTO_PRIVATE_KEY_SEED`
- `RH_CRYPTO_BASE_URL`
- `RH_LIVE_TRADING`
- `RH_LIVE_CONFIRM`
- `ADMIN_USER_ID`
- safety/reconcile intervals

## Operational Flow

1. `scripts/crypto_healthcheck`
   - fetches balances + holdings
   - writes snapshots + reconciliation event
   - prints PASS/FAIL
2. `scripts/crypto_smoke_trade`
   - defaults to paper mode
   - if live gates are satisfied, sends a tiny `$1` test order
   - polls fills and reconciles snapshots

## Admin Controls

- `/crypto_live_on I UNDERSTAND THIS IS REAL MONEY`
- `/crypto_live_off`
- `/crypto_status`
- `/crypto_buy <symbol> <notional>`
- `/crypto_sell <symbol> <notional|qty>`
- `/crypto_pause`
- `/crypto_resume`

Non-admin users receive a denial message without exposing tool traces.

## Kill Switch

To immediately halt live trading:

1. `/crypto_pause`
2. set `RH_LIVE_TRADING=false`
3. clear `RH_LIVE_CONFIRM`
4. rerun `scripts/crypto_healthcheck`

## Risks

This executes **real-money** crypto orders when live gates are enabled. Start with tiny notionals and verify reconciliation health before scaling.
