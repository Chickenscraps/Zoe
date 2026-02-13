# Progress — Zoe Trading Engine Hardening

## Phase 1: P&L Bug Fix + Fastest Data Refresh ✅

### What Changed
- **P&L Fix**: Added `pendingBuyNotional` to `totalValue` in Overview.tsx so money in open orders no longer shows as a loss
- **"In Orders" KPI card**: Added 4th KPI showing money allocated to pending buy orders
- **Supabase Realtime**: Created `useRealtimeSubscriptions.ts` hook for near-instant updates on orders, fills, prices, cash
- **Targeted fetches**: Added `fetchOrders`, `fetchFills`, `fetchCash` functions called by realtime callbacks (no full re-fetch)
- **Polling reduced**: Full refresh 30s→60s (fallback), price poll 5s→2s (fallback); realtime handles primary updates
- **Equity chart**: Now includes pending order notional in equity points

### Files Modified
- `zoe-terminal/src/pages/Overview.tsx` — P&L fix + KPI card
- `zoe-terminal/src/hooks/useDashboardData.ts` — Polling intervals, pendingBuyNotional, realtime wiring
- `zoe-terminal/src/hooks/useRealtimeSubscriptions.ts` — NEW: Supabase Realtime hook

---

## Phase 2: Paper Mode Correctness ✅

### What Changed
- **Paper BUY creates fills**: Orders, fills, holdings, and cash snapshots all updated on paper buys
- **Paper EXIT creates fills**: Sell fills, holdings removal, cash return all recorded
- **Equity = cash + holdings**: Fixed `equity = buying_power` → `equity = cash + sum(qty * mid)`
- **getattr bug fixed**: `getattr(self.repo, "fills", [])` → `self.repo.recent_fills(self.mode, limit=500)`
- **Scanner score clamped**: Total score now clamped to 100 max

### Files Modified
- `services/crypto_trader/trader.py` — Paper fills, equity fix, getattr fix, safe mode
- `services/crypto_trader/scanner.py` — Score clamping
- `services/crypto_trader/repository.py` — Protocol kwargs fix

---

## Phase 3: Order Lifecycle Schema + OrderManager ✅

### What Changed
- **Migration**: `order_events` (append-only transition log), `order_intents` (why behind an order chain), `trade_locks`, extended `crypto_orders` with repositioning columns
- **OrderManager**: State machine with submit_intent → poll_and_manage → reposition → cancel; tracks orders in memory with DB persistence
- **Reposition Policy**: Configurable TTL, step BPS, max cross spread, liquidity guard
- **Paper Broker**: Simulated fills with slippage for paper trading

### Files Created
- `migrations/20260213_order_lifecycle.sql`
- `services/crypto_trader/order_manager.py`
- `services/crypto_trader/reposition_policy.py`
- `services/crypto_trader/paper_broker.py`

### Files Modified
- `zoe-terminal/src/lib/types.ts` — New table types + extended crypto_orders

---

## Phase 5: Enhanced Dashboard ✅

### What Changed
- **OpenOrdersTable**: Added columns for Limit price, Age (live countdown), Replace count (R#), Next action countdown, Stuck order detection
- **AlertBanner**: Alerts for stuck orders, API degraded, repeated rejects
- **Realtime for order_events**: Subscribed to `order_events` INSERT for live timeline updates

### Files Modified
- `zoe-terminal/src/components/OpenOrdersTable.tsx` — Enhanced with lifecycle columns
- `zoe-terminal/src/components/AlertBanner.tsx` — NEW: Alert banners
- `zoe-terminal/src/pages/Overview.tsx` — Added AlertBanner
- `zoe-terminal/src/hooks/useRealtimeSubscriptions.ts` — Added order_events subscription

---

## Phase 6: Coordination + Safety ✅

### What Changed
- **Trade locks**: `trade_locks` table in migration for dual-engine collision prevention
- **Reconciliation tolerance**: Configurable via `RECONCILE_CASH_TOLERANCE` ($2 default) and `RECONCILE_QTY_TOLERANCE` (0.000001 default)
- **Safe mode**: Activates after N consecutive empty scans (`SAFE_MODE_EMPTY_SCAN_THRESHOLD`, default 3); 5-minute cooldown

### Files Modified
- `services/crypto_trader/config.py` — New config knobs
- `services/crypto_trader/trader.py` — Configurable tolerance, empty scan safe mode

---

## Phase 7: Tests ✅

### Test Files
- `services/crypto_trader/test_order_state_machine.py` — OrderManager transitions, cancel, recovery
- `services/crypto_trader/test_reposition_policy.py` — TTL, decisions, price stepping, caps
- `services/crypto_trader/test_paper_lifecycle.py` — Full BUY → EXIT cycle with fills + P&L

### Frontend Build
- `cd zoe-terminal && npx vite build` — Passes ✅

---

## How to Run

```bash
# Dashboard
cd zoe-terminal && npm run dev   # http://localhost:5180

# Crypto Trader (paper)
python -m services.crypto_trader.trader

# Run migration
# Apply migrations/20260213_order_lifecycle.sql to Supabase

# Run tests
pytest services/crypto_trader/test_order_state_machine.py -v
pytest services/crypto_trader/test_reposition_policy.py -v
pytest services/crypto_trader/test_paper_lifecycle.py -v
```
