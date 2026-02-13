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
