# Phase 0 — Current State Inventory

## 1. Supabase Tables (28 total)

### Core Trading Tables (mode-scoped)
| Table | Key Columns | Mode? | Writer | Reader |
|-------|-------------|-------|--------|--------|
| `crypto_orders` | id, client_order_id, symbol, side, order_type, qty, notional, status, requested_at, raw_response | ✅ | CryptoTraderService | Dashboard (useDashboardData) |
| `crypto_fills` | id, order_id, fill_id, symbol, side, qty, price, fee, executed_at, raw_fill | ✅ | CryptoTraderService | Dashboard (useDashboardData) |
| `crypto_cash_snapshots` | id, taken_at, cash_available, buying_power, source | ✅ | CryptoTraderService reconcile | Dashboard (useDashboardData, equity chart) |
| `crypto_holdings_snapshots` | id, taken_at, holdings (jsonb), total_crypto_value, source | ✅ | CryptoTraderService reconcile | Dashboard (useDashboardData) |
| `crypto_reconciliation_events` | id, taken_at, local_cash, rh_cash, cash_diff, local_holdings, rh_holdings, holdings_diff, status, reason | ✅ | CryptoTraderService | Dashboard health check |
| `daily_notional` | day, amount, notional_used, notional_limit | ✅ | CryptoTraderService | Dashboard, Settings |

### Scanner & Intelligence Tables (mode-scoped)
| Table | Key Columns | Mode? | Writer | Reader |
|-------|-------------|-------|--------|--------|
| `candidate_scans` | id, instance_id, symbol, score, score_breakdown (jsonb), info (jsonb), recommended_strategy, created_at | ✅ | Scanner (crypto_trader) | Dashboard, Scanner page, Charts page, Intelligence |
| `thoughts` | id, instance_id, content, type, symbol, created_at, metadata (jsonb) | ✅ | CryptoTraderService | Intelligence > Thoughts |
| `crypto_candles` | id, symbol, timeframe, open_time, open, high, low, close, volume, patterns (jsonb) | ✅ | CandleManager | Charts page (useCandleData) |

### Structure Tables (mode-scoped)
| Table | Key Columns | Mode? | Writer | Reader |
|-------|-------------|-------|--------|--------|
| `market_pivots` | id, symbol, timeframe, timestamp, price, type (high/low), source, atr_snapshot, confirmed | ✅ | structure_context.py | Intelligence > Structure |
| `technical_trendlines` | id, symbol, timeframe, side, slope, intercept, start_at, end_at, inlier_count, score, is_active | ✅ | structure_context.py | Intelligence > Structure |
| `technical_levels` | id, symbol, timeframe, price_centroid, price_top, price_bottom, role, touch_count, score, is_active | ✅ | structure_context.py | Intelligence > Structure |
| `structure_events` | id, symbol, timeframe, event_type (breakout/breakdown/retest), reference_id, price_at, confirmed | ✅ | structure_context.py | Intelligence > Structure |
| `bounce_events` | id, ts, symbol, prev_state, state, score, reason_json | ✅ | structure_context.py | Intelligence > Structure |
| `bounce_intents` | id, ts, symbol, entry_style, entry_price, tp_price, sl_price, score, blocked, executed | ✅ | structure_context.py | Intelligence > Structure |

### Edge Factory Tables (NOT mode-scoped — critical finding)
| Table | Key Columns | Mode? | Writer | Reader |
|-------|-------------|-------|--------|--------|
| `ef_features` | id, symbol, feature_name, value, computed_at, source, metadata | ❌ | SupabaseFeatureRepository | Edge Factory |
| `ef_regimes` | id, regime, confidence, detected_at, features_used | ❌ | SupabaseFeatureRepository | Edge Factory |
| `ef_signals` | id, symbol, direction, strength, features, generated_at, strategy_name, acted_on | ❌ | SupabaseFeatureRepository | Edge Factory |
| `ef_positions` | id, symbol, side, entry_price, entry_time, size_usd, tp_price, sl_price, status, exit_price, exit_time, pnl_usd | ❌ | SupabaseFeatureRepository | Edge Factory |
| `ef_state` | key, value (jsonb), updated_at | ❌ | SupabaseFeatureRepository | Edge Factory |

### System / Config Tables
| Table | Key Columns | Mode? | Writer | Reader |
|-------|-------------|-------|--------|--------|
| `health_heartbeat` | id, instance_id, component, status, last_heartbeat, details | ✅ | CryptoTraderService | Dashboard |
| `pnl_daily` | date, instance_id, daily_pnl, equity, drawdown, win_rate | ✅ | CryptoTraderService | Dashboard equity chart |
| `agent_state` | id, mode, instance_id, state (jsonb), updated_at | ✅ | Boot reconciler | Boot reconciler |
| `boot_audit` | id, run_id, mode, instance_id, started_at, status, diffs, integrity_checks | ✅ | Boot reconciler | — |
| `config` | key, instance_id, value (jsonb) | — | — | Settings page |
| `audit_log` | id, instance_id, event_type, message, created_at, metadata | — | — | — |
| `risk_events` | id, instance_id, event_type, severity, message | — | — | — |
| `zoe_events` | id, source, subtype, severity, title, body, symbol, metadata | ✅ | CopilotSidebar | CopilotSidebar |
| `copilot_messages` | id, user_id, role, content, context_page | ✅ | CopilotSidebar | CopilotSidebar |

### Legacy / Unused Tables
| Table | Notes |
|-------|-------|
| `positions` | Old equities positions table (account_id based) — not used by crypto |
| `trades` | Old equities trade log — not used by crypto |
| `daily_gameplans` | Not populated by current code |
| `daily_gameplan_items` | Not populated by current code |
| `crypto_tickers` | Referenced in types but no active writer found |

## 2. RPC Functions
| Function | Args | Called By |
|----------|------|-----------|
| `get_account_overview` | p_discord_id, p_mode | useDashboardData |
| `get_activity_feed` | p_limit, p_mode | useDashboardData |
| `get_positions_report` | p_account_id | (defined but may not be actively called) |

## 3. Polling Cadences (Frontend)
| Hook | Interval | Tables Hit | Notes |
|------|----------|------------|-------|
| useDashboardData (full) | 30s | 12 queries in parallel | Heavy payload |
| useDashboardData (prices) | 5s | candidate_scans x2 | Fast price poll |
| useCandleData | 60s | crypto_candles, candidate_scans | Per symbol+timeframe |
| useStructureData | 30s | 6 queries in parallel | market_pivots, trendlines, levels, events, bounces, intents |
| Intelligence > candidates | 30s | candidate_scans | Separate from dashboard |
| Intelligence > consensus | 30s | candidate_scans x2 | Separate from dashboard |
| Intelligence > thoughts | 15s | thoughts | Fastest poll |

### Total Supabase Requests Per Minute (estimated):
- Dashboard page active: ~28 queries/min (12 full + 12 price + 4 from realtime)
- Charts page: ~2 queries/min per symbol
- Intelligence page: ~16 queries/min (candidates + consensus + thoughts + structure)
- **Peak (all pages open)**: ~46+ queries/min

## 4. Realtime Subscriptions
**None currently active.** All data is fetched via polling. No `.channel()` or `.on()` usage found in frontend code.

## 5. Mode Isolation Status

### ✅ Properly Mode-Scoped
- All `useDashboardData` queries → `.eq('mode', mode)`
- All `useCandleData` queries → `.eq('mode', mode)`
- All `useStructureData` queries → `.eq('mode', mode)`
- Intelligence page queries → `.eq('mode', mode)`
- Scanner page → `useModeContext()`
- `SupabaseCryptoRepository` → mode passed as parameter

### ❌ NOT Mode-Scoped (CRITICAL)
- `SupabaseFeatureRepository` (Edge Factory) — **NO MODE COLUMN** on ef_features, ef_regimes, ef_signals, ef_positions, ef_state
- If paper and live Edge Factory instances run simultaneously, they share the same feature/signal/position state
- This is the most critical schema issue

## 6. Security
- **No RLS policies** — all tables are wide open
- Frontend uses **anon key** (VITE_SUPABASE_ANON_KEY)
- Backend uses **service role key** (SUPABASE_SERVICE_ROLE_KEY / SUPABASE_SERVICE_KEY)
- Anon key can read AND write to all tables (no RLS = full access)
- No authentication — anonymous access

## 7. Missing Indexes (likely)
No explicit index creation found in codebase. Default primary key indexes only. Missing:
- `candidate_scans(mode, created_at DESC)` — hit every 5s for price polling
- `crypto_candles(symbol, timeframe, mode, open_time)` — unique constraint exists via upsert
- `thoughts(mode, created_at DESC)` — polled every 15s
- `crypto_cash_snapshots(mode, taken_at DESC)` — used for equity chart (2000 rows)
- `crypto_fills(mode, executed_at DESC)` — sorted for P&L calculation

## 8. Schema Drift
- `zoe_events` table exists in types.ts but no active writer in Python backend
- `copilot_messages` exists in types.ts but only used by CopilotSidebar component
- `daily_gameplans` / `daily_gameplan_items` — defined but never populated
- `crypto_tickers` — defined but no active writer
- `config` table — referenced in Settings page but shows "No stored configuration keys"
