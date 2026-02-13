# Progress Log — Kraken Migration + System Hardening

## Phase 0 — Repo Orientation + Scaffolding
**Status**: Complete
**Date**: 2026-02-13

### Baseline Architecture
- **Trading engines**: Python (Edge Factory + CryptoTrader) with Robinhood REST API
- **Broker coupling**: `self.rh` in `live_executor.py`, `quote_model.py`, `order_manager.py`, `runner.py`; `self.client` in `trader.py`
- **Database**: Supabase Postgres — tables for accounts, orders, fills, positions, pnl_daily, cash/holdings snapshots, health, config
- **Dashboard**: React 19 + Vite + Tailwind (`zoe-terminal/`), polling 30s full + 5s prices from `candidate_scans`
- **Market data**: Polygon REST (equities) + Robinhood REST (crypto bid/ask) — no WebSocket
- **Account output problem**: uses `buying_power` from `crypto_cash_snapshots`, unrealized P&L hardcoded to 0, no fee attribution, no deposit/withdrawal ledger

### What Needs to Change
1. Replace Robinhood broker with Kraken (REST + WebSocket)
2. Add market catalog + two-tier WS market watch (focus/scout)
3. Fix accounting: real equity, FIFO P&L, fee tracking, deposit/withdrawal ledger
4. Add order lifecycle state machine + repositioner for stale orders
5. Harden: startup hydration, reconciliation, rate limiting, correlation IDs, Ops Console
6. Dashboard: virtualized market table, realtime subscriptions, proper P&L display

---

## Phase 1 — Kraken Credentials + Connectivity
**Status**: Complete
**Date**: 2026-02-13

### 1a — Secrets Wiring
- Parsed `kraken.txt` (API key + API secret only, ignored username/password)
- Stored in `.env` as `KRAKEN_API_KEY`, `KRAKEN_API_SECRET`, `EXCHANGE=kraken`
- Updated `.gitignore`: added `kraken.txt`, `*.key`, `*.pem`, broadened `.env.*`
- Updated `.env.example` with Kraken config section

### 1b — KrakenClient REST
- Created `integrations/kraken_client/` package (config, client, ws, symbols)
- HMAC-SHA512 signing with nonce-based auth
- Full REST methods: balance, holdings, place_order, get_order, get_order_fills, get_best_bid_ask, get_best_bid_ask_batch, get_trading_pairs, cancel_order, get_ws_token
- Built-in rate limiter (token bucket), retry with backoff
- `place_order` handles Kraken's qty requirement: computes `qty = notional / price`
- Response normalization: `get_best_bid_ask` returns `{"results": [...]}` matching RH format

### 1c — KrakenWebSocket (WS v2)
- Public: `wss://ws.kraken.com/v2` — ticker, book, trades
- Private: `wss://ws-auth.kraken.com/v2` — auth token from REST
- Auto-reconnect with exponential backoff + jitter
- Callback-based: `on_ticker()`, `on_book()`, `on_trade()`, `on_execution()`
- Fixed race condition: `asyncio.Event` for connect-before-subscribe
- Fixed WS v2 symbol format: uses BTC/USD (not XBT/USD like v1)

### 1d — Symbol Normalization + ExchangeClient Protocol
- `integrations/kraken_client/symbols.py`: dynamic cache from AssetPairs (1482 pairs)
- Handles REST (XXBTZUSD), WS v1 (XBT/USD), WS v2 (BTC/USD) formats
- `integrations/exchange_protocol.py`: `ExchangeClient` Protocol (runtime_checkable)

### 1e — Exchange Adapter Wiring
- **Edge Factory**: `self.rh` → `self.exchange` across live_executor, quote_model, order_manager, account_state
- **runner.py**: `_build_rh_client()` → `_build_exchange_client()` with `EXCHANGE` env var feature flag
- **orchestrator.py**: `_rh_client` → `_exchange_client`, heartbeat component `robinhood_api` → `exchange_api`
- **market_ingestor.py**: `rh_client` → `exchange_client`, `self._rh` → `self._exchange`
- **CryptoTrader**: `trader.py` accepts generic client (no RH type annotation), reconciliation handles both Kraken/RH balance formats
- **broker.py**: Added `KrakenBroker` alongside existing `RobinhoodBroker`
- **__main__.py**: `_build_exchange_client()` with EXCHANGE env var, lazy imports
- **boot/reconcile.py** + **boot/broker_reconciler.py**: removed RH type annotations, handles Kraken balance format
- **scanner.py** + **market_data.py**: removed RH type annotations

### 1f — Smoke Tests
- `integrations/kraken_client/test_connectivity.py`: 6/6 tests passed
  - system_status, tradable_pairs, balance, open_orders, ws_public, ws_private
- Verified: XXBT balance 0.00214748, 1482 tradable pairs, WS ticker + private auth working

---

## Phase 2 — Market Catalog + Adaptive Market Watch
**Status**: Complete
**Date**: 2026-02-13

### 2a — Database Migration
- Created `migrations/20260213_market_data_tables.sql`
- New tables: `market_catalog`, `market_snapshot_focus`, `market_snapshot_scout`, `market_sparkline_points`, `mover_events`, `market_focus_config`
- Indexes on `updated_at` for focus/scout, `detected_at` for movers
- RLS policies, realtime publication enabled on focus + mover_events

### 2b — Market Data WS Service (`services/market_data_ws/`)
- **config.py**: `MarketDataConfig` with env vars — focus flush 1s, scout flush 30s, mover thresholds
- **catalog.py**: `MarketCatalog` discovers pairs from Kraken `AssetPairs`, upserts to `market_catalog` table
- **coalescer.py**: `Coalescer` with `TickerSnapshot` dataclass, timer-based batch flush, dirty tracking per symbol
- **snapshot_writer.py**: `SnapshotWriter` for focus/scout/sparkline/mover upserts with write stats tracking
- **focus_manager.py**: `FocusManager` with promote/demote, DB persistence (`market_focus_config`), stale mover expiry
- **mover_detector.py**: `MoverDetector` with 1h momentum calculation, price history deque, volume acceleration

### 2c — Entry Point (`__main__.py`)
- Startup sequence: catalog refresh → focus setup → WS subscribe → coalescers → sparkline/expiry loops
- Routes WS ticker updates to focus or scout coalescer based on FocusManager membership
- Batch subscription (50 symbols per batch) with max pairs cap
- Background tasks: sparkline loop, mover expiry loop, periodic stats logging

### 2d — Dashboard: Types + Hooks
- **types.ts**: Added type definitions for all 6 new market tables
- **useMarketData.ts**: `useFocusData()` (Supabase realtime), `useScoutData()` (30s polling), `useMoverAlerts()` (realtime), `useMarketData()` (combined focus + scout into `MarketRow[]`)

### 2e — Dashboard: Markets Page
- **Markets.tsx**: Full page with tabs (All / Focus / Gainers / Losers / Movers), search bar, sortable columns
- Columns: Symbol, Price, 24h Change, Volume, Spread, Bid, Ask
- Color-coded changes (green/red), formatted prices, mover event indicators

### 2f — Dashboard: FocusPanel + Integration
- **FocusPanel.tsx**: Compact grid tiles for focus-universe pairs (live bid/ask/change/spread)
- **AppShell.tsx**: Added "Markets" nav item with Globe icon
- **App.tsx**: Added `/markets` route
- **Overview.tsx**: Integrated `<FocusPanel />` above legacy "Live Prices" section

---

## Phase 3 — Accounting Overhaul
**Status**: Complete
**Date**: 2026-02-13

### 3a — FIFO Cost-Basis Matcher (`services/accounting/fifo_matcher.py`)
- `FIFOMatcher`: processes fills chronologically, maintains open lots per symbol
- On sell: pops oldest buy lots (FIFO), computes `realized = (sell - buy) * qty - fees`
- Methods: `get_realized_pnl()`, `get_unrealized_pnl(sym, mark)`, `get_cost_basis()`, `get_open_qty()`
- `from_fills()` class method builds matcher from fill dicts

### 3b — Equity Calculator (`services/accounting/equity_calculator.py`)
- `EquityCalculator`: MTM portfolio valuation using focus snapshot marks
- `compute()` returns `EquityBreakdown`: cash, crypto_value, total_equity, realized/unrealized P&L, fees
- `PositionMark`: per-position detail (qty, cost_basis, mark_price, market_value, unrealized_pnl)
- Falls back to exchange REST for marks not in focus snapshots

### 3c — Fee Tracker + Cash Event Ledger
- **fee_tracker.py**: `FeeTracker` — persists per-fill fees to `fee_ledger` table, queries by symbol/mode
- **cash_event_ledger.py**: `CashEventLedger` — records deposits/withdrawals to `cash_events` table, net deposits calculation
- **mark_to_market.py**: `MarkToMarket` — reads mark prices from focus snapshots with staleness detection

### 3d — Database Migration (`migrations/20260213_accounting_tables.sql`)
- Extended `crypto_fills`: +broker_fee, fee_currency, broker_fill_id, exchange columns
- New `cash_events` table: deposits/withdrawals with event_type, amount, currency
- New `fee_ledger` table: per-fill fee attribution with fill_id unique constraint
- Extended `pnl_daily`: +fees_paid, gross_equity, net_equity, net_deposits, crypto_value, cash_usd

### 3e — Backend Integration
- **orchestrator.py** `_write_pnl_snapshot()`: now uses FIFOMatcher for realized P&L + focus snapshot marks for unrealized P&L
- **account_state.py**: new `cash_usd`, `crypto_value` properties; `_fetch_crypto_mark_value()` reads focus snapshots; equity = cash + crypto MTM
- **runner.py**: wires Supabase client into AccountState for mark-to-market lookups
- **trader.py** `_write_pnl_snapshot()`: uses FIFOMatcher + focus marks for enriched pnl_daily rows
- **repository.py** + **supabase_repository.py**: added `get_fills()` method

### 3f — Dashboard Updates
- **useDashboardData.ts**: sources realized/unrealized/fees from pnl_daily enriched columns; falls back to client-side FIFO; exports `unrealizedPnl`, `totalFees`
- **types.ts**: extended pnl_daily (+fees_paid, crypto_value, cash_usd), crypto_fills (+broker_fee, exchange), added cash_events and fee_ledger types
- **Overview.tsx**: new P&L breakdown row with Realized P&L, Unrealized P&L, and Fees Paid KPI cards

---

## Phase 4 — Order Lifecycle + Repositioning
**Status**: Complete
**Date**: 2026-02-13

### 4a — Order Intent System (`services/order_lifecycle/intent.py`)
- `OrderIntent` dataclass with full state machine (11 states, valid transitions enforced)
- `IntentManager`: creates/updates intents in Supabase with idempotency_key dedup
- States: created → submitted → acked → partial_fill → filled / cancelled / replaced / rejected / expired / error
- Terminal states: filled, cancelled, replaced, rejected, expired

### 4b — Order Event Log (`services/order_lifecycle/event_log.py`)
- `OrderEventLog`: append-only audit trail per intent
- Records: event_type, broker_order_id, fill_price, fill_qty, fee, metadata
- Query by intent_id or recent events across all intents

### 4c — Repositioner (`services/order_lifecycle/repositioner.py`)
- `Repositioner`: async loop checking for stale orders every 30s
- TTL-based staleness: configurable order_ttl_sec (default 120s)
- On stale: cancel on exchange → fetch fresh mark → widen limit by chase_step_pct → create replacement intent
- Max reposition attempts (default 3) before final cancellation
- Handles partial fills (repositions only remaining_qty)
- Configurable via env vars: REPO_CHECK_INTERVAL_SEC, REPO_ORDER_TTL_SEC, REPO_CHASE_STEP_PCT, REPO_MAX_ATTEMPTS

### 4d — Trade Lock (`services/order_lifecycle/trade_lock.py`)
- `TradeLock`: distributed locking via Supabase trade_locks table
- PK on (symbol, engine, mode) for INSERT ON CONFLICT DO NOTHING pattern
- acquire/release with holder_id verification
- Prevents Edge Factory and CryptoTrader from trading same symbol simultaneously

### 4e — Safe Mode (`services/order_lifecycle/safe_mode.py`)
- `SafeMode`: monitors market data staleness + API error rate
- Market data check: focus snapshot age > 60s → halt entries
- API health: 3+ errors in 5 min → halt entries, allow exits only
- Auto-recovery when conditions clear
- Publishes status to health_heartbeat for dashboard alerts

### 4f — Database Migration (`migrations/20260213_order_lifecycle_tables.sql`)
- `order_intents`: idempotency_key unique, status enum, broker_order_id, fill data, metadata
- `order_events`: FK to intents, append-only, event_type + execution data
- `trade_locks`: PK (symbol, engine, mode), lock_holder for ownership
- Partial index on active intents for fast queries
- RLS policies for dashboard read access

### 4g — Dashboard Types
- **types.ts**: added order_intents, order_events, trade_locks table types

---

## Phase 5 — Performance + Reliability Hardening
**Status**: Complete
**Date**: 2026-02-13

### 5a — Startup Hydration (`services/reconciliation/hydration.py`)
- `StartupHydrator`: executes hydration sequence before trading begins
- Steps: catalog check → exchange balances + holdings → open order intents → reconciliation → heartbeat
- Returns `HydrationResult` with cash, holdings, open_orders, errors, ready status

### 5b — Reconciliation Engine (`services/reconciliation/broker_vs_db.py`)
- `BrokerReconciler`: compares exchange state vs DB state
- Detects: cash mismatch (>$0.01 tolerance), position qty diffs, orphaned/missing positions
- Returns `ReconciliationResult` with status, diffs, details
- Writes reconciliation events to `crypto_reconciliation_events` table

### 5c — Ops Console (`zoe-terminal/src/pages/Ops.tsx`)
- System status banner: HEALTHY / DEGRADED / SAFE_MODE with color coding
- Component health grid: per-component heartbeat status + last update time
- Active order intents table: symbol, side, limit, qty, status, engine, created
- Trade locks display: symbol, engine, lock time
- Latest reconciliation: exchange vs DB cash, holdings diffs
- Auto-refreshes every 10s

### 5d — Dashboard Integration
- **AppShell.tsx**: added "Ops" nav item with Shield icon
- **App.tsx**: added `/ops` route

---

## Phase 6 — Tests + Gating
**Status**: Complete
**Date**: 2026-02-13

### 6a — Unit Tests (66 tests, all passing)

**`tests/test_fifo_matcher.py`** — 12 tests for FIFO cost-basis matching:
- simple_buy_sell_round_trip, fifo_order, partial_lot_consumption
- fees_reduce_realized_pnl, multi_symbol, unrealized_pnl, unrealized_pnl_with_fees
- sell_more_than_bought, from_fills_classmethod, cost_basis_multiple_lots
- empty_matcher, total_fees_tracking

**`tests/test_order_intent.py`** — 9 tests for order lifecycle state machine:
- initial_state, valid_transitions (15 cases), invalid_transitions (6 cases)
- terminal_states, non_terminal_states, transition_updates_timestamp
- all_states_covered_in_transitions, default_values, custom_values

**`tests/test_coalescer.py`** — 8 tests for market data coalescer:
- TickerSnapshot default/custom values
- update_stores_latest, multiple_symbols, dirty_tracking, stats_tracking
- mid_and_spread_computed, get_nonexistent_symbol

**`tests/test_symbol_normalization.py`** — 37 tests for Kraken symbol normalization:
- _normalize_asset: XXBT→BTC, XETH→ETH, ZUSD→USD, SOL unchanged, XXDG→DOGE, XBT→BTC
- _convert_wsname_to_v2: XBT→BTC, XDG→DOGE, ETH unchanged, no-slash passthrough
- to_kraken: REST and WS formats for BTC/ETH/SOL/DOGE, unknown fallbacks
- from_kraken: REST, WS v2, WS v1, altname, unknown
- Round-trip: REST and WS for BTC/ETH/SOL/DOGE/XRP (parametrized)
- Cache population: pair count, get_all_symbols

### 6b — Test Infrastructure
- Mock AssetPairs fixture for symbol tests (autouse, with save/restore of global cache)
- All tests are pure unit tests — no network, no Supabase, no async runtime needed

---
