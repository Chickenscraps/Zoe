# Ops Runbook — Zoe Trading Engine

## Services

| Service | How to Start | Port |
|---------|-------------|------|
| Zoe Terminal (Dashboard) | `cd zoe-terminal && npm run dev` | 5180 |
| Crypto Trader | `python -m services.crypto_trader.trader` | — |
| Edge Factory | `EDGE_FACTORY_MODE=paper python -m services.edge_factory.runner` | — |

## Config Knobs

### Order Repositioning (env vars)
| Var | Default | Description |
|-----|---------|-------------|
| `ORDER_TTL_SECONDS_ENTRY` | 60 | Seconds before repricing an entry order |
| `ORDER_TTL_SECONDS_EXIT` | 30 | Seconds before repricing an exit order |
| `MAX_REPRICE_ATTEMPTS` | 3 | Max cancel/replace cycles |
| `REPRICE_STEP_BPS` | 5 | Basis points per step toward mid |
| `MAX_CROSS_SPREAD_BPS` | 20 | Cap on how far to cross spread |
| `LIQUIDITY_GUARD_SPREAD_PCT` | 0.5 | Abort reposition if spread > this % |

### Risk Controls
| Var | Default | Description |
|-----|---------|-------------|
| `MAX_NOTIONAL_PER_TRADE` | 25 | Max USD per trade |
| `MAX_DAILY_NOTIONAL` | 50 | Max USD per day |
| `MAX_OPEN_POSITIONS` | 3 | Max concurrent positions |
| `STOP_TRADING_ON_DEGRADED` | true | Halt if reconciliation mismatch |
| `RECONCILE_CASH_TOLERANCE` | 2.0 | USD tolerance for cash mismatch |
| `RECONCILE_QTY_TOLERANCE` | 0.000001 | Qty tolerance for holdings mismatch |
| `SAFE_MODE_EMPTY_SCAN_THRESHOLD` | 3 | Consecutive empty scans before safe mode |

### Kill Switch
- Dashboard header toggle: writes `kill_switch` key to `config` table
- Manual: `UPDATE config SET value = 'true' WHERE key = 'kill_switch';`

## Database Tables (New)

| Table | Purpose |
|-------|---------|
| `order_intents` | Records the "why" behind an order chain |
| `order_events` | Append-only log of every order state transition |
| `trade_locks` | Prevents dual-engine symbol collisions |

### New Columns on `crypto_orders`
| Column | Type | Purpose |
|--------|------|---------|
| `intent_group_id` | UUID | Links orders in a cancel/replace chain |
| `replace_count` | INT | How many times this order has been repriced |
| `cancel_reason_code` | TEXT | Why the order was canceled |
| `remaining_qty` | NUMERIC | Qty left after partial fills |
| `ttl_seconds` | INT | Time before next reposition check |
| `next_action_at` | TIMESTAMPTZ | When the next reposition fires |
| `parent_order_id` | UUID | Previous order in the chain |
| `limit_price` | NUMERIC | Limit price for limit orders |

## Failure Modes

### Stuck Order
- **Symptom**: Order in WORKING state for > 5 min with replace_count >= max
- **Dashboard**: Alert banner shows "stuck orders" warning with count
- **Action**: Manual cancel via dashboard or SQL: `UPDATE crypto_orders SET status = 'canceled' WHERE id = '...'`

### API Degraded
- **Symptom**: Robinhood API returning errors, health_heartbeat shows warning/error
- **Dashboard**: Alert banner shows "System degraded" with reason
- **Action**: System enters safe_mode (halts new entries, allows exits). Check RH status page.

### Reconciliation Mismatch
- **Symptom**: crypto_reconciliation_events shows status='degraded'
- **Action**: Check cash_diff and holdings_diff. If within tolerance, increase `RECONCILE_CASH_TOLERANCE` or `RECONCILE_QTY_TOLERANCE`. If real drift, investigate fills.

### Consecutive Empty Scans
- **Symptom**: Scanner returns 0 candidates N times in a row
- **Action**: Safe mode activates for 5 minutes. Check API connectivity and watchlist.

### Repeated Order Rejections
- **Symptom**: 3+ orders rejected in 10 minutes
- **Dashboard**: Alert banner shows rejection count
- **Action**: Check broker account status, buying power, and symbol availability.

## Recovery

### After Crash/Restart
1. OrderManager calls `recover_from_db()` on boot
2. Loads all WORKING/PARTIAL/CANCEL_PENDING orders
3. Reconciles with broker state
4. Resumes repositioning timers

### Rollback
1. Revert migrations: DROP new tables/columns
2. Revert code: git checkout main
3. Redeploy zoe-terminal to Netlify

## Data Refresh Architecture

### Primary: Supabase Realtime
- `crypto_orders` INSERT/UPDATE → instant order refresh
- `crypto_fills` INSERT → instant fill + order refresh
- `candidate_scans` INSERT → instant price refresh
- `crypto_cash_snapshots` INSERT → instant cash refresh
- `order_events` INSERT → instant order timeline refresh

### Fallback: Polling
- Full dashboard refresh: every 60s
- Price-only refresh: every 2s
- Activates automatically if WebSocket disconnects
