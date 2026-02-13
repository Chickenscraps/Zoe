# Supabase Backend Audit — Ranked Findings & Fixes

## Priority Legend
- 🔴 P0 — Data integrity / security risk, fix ASAP
- 🟠 P1 — Correctness issue that can cause wrong data
- 🟡 P2 — Performance / reliability improvement
- 🟢 P3 — Nice-to-have / observability

---

## 🔴 P0-1: Edge Factory Tables Missing Mode Column

**Finding:** `ef_features`, `ef_regimes`, `ef_signals`, `ef_positions`, `ef_state` have **no `mode` column**. If paper and live Edge Factory instances run simultaneously, they share the same data.

**Impact:** Live trades could use paper regime/signal data (or vice versa). Position state could be corrupted across modes.

**Fix:** Add `mode TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('paper','live'))` to all 5 `ef_*` tables. Update `SupabaseFeatureRepository` to filter by mode on every query.

---

## 🔴 P0-2: No RLS — Anon Key Has Full Write Access

**Finding:** No Row Level Security policies on any table. The frontend anon key can INSERT/UPDATE/DELETE on all tables including `crypto_orders`, `crypto_fills`, `ef_positions`.

**Impact:** Anyone with the anon key (visible in the frontend bundle) can manipulate trade data, inject fills, or delete reconciliation events.

**Fix:** Enable RLS on all tables. Anon key → read-only on dashboard tables. Service role key → full write access (used only from Python backend). See Phase 3 migration.

---

## 🔴 P0-3: No Idempotency Keys on Orders/Fills

**Finding:** `crypto_orders` has no idempotency_key. `crypto_fills` has `fill_id` unique constraint but no broker-side order ID enforcement. If the bot crashes mid-order and restarts, it could submit duplicate orders.

**Impact:** Duplicate trades, double-spending of notional limits.

**Fix:** Add `idempotency_key TEXT UNIQUE` and `broker_order_id TEXT` to `crypto_orders`. Add `trace_id TEXT` for end-to-end tracing. Backend must generate idempotency keys before submission.

---

## 🟠 P1-1: Excessive Polling — 46+ Queries/Min at Peak

**Finding:** Frontend polls 12 tables every 30s (dashboard), 2 tables every 5s (prices), 6 tables every 30s (structure), 1 table every 15s (thoughts), plus separate Intelligence queries. Total: ~46+ queries/min with all pages open.

**Impact:** High Supabase bill, slow mobile experience, unnecessary battery drain on phones.

**Fix:**
1. **Immediate:** Replace price polling with Supabase Realtime subscription on `candidate_scans`
2. **Medium-term:** Implement local-first event store with SSE push (Phase 6)
3. **Quick win:** Deduplicate Intelligence queries — reuse useDashboardData's `livePrices` instead of separate consensus fetch

---

## 🟠 P1-2: Missing Critical Indexes

**Finding:** No explicit indexes beyond primary keys. The most-queried patterns are:
- `candidate_scans WHERE mode=X ORDER BY created_at DESC` (every 5s)
- `crypto_cash_snapshots WHERE mode=X ORDER BY taken_at DESC LIMIT 2000` (30s, returns 2000 rows)
- `thoughts WHERE mode=X ORDER BY created_at DESC` (every 15s)
- `crypto_candles WHERE symbol=X AND timeframe=X AND mode=X ORDER BY open_time` (every 60s)

**Impact:** Full table scans on every poll. Especially bad on `crypto_cash_snapshots` which returns 2000 rows for the equity chart.

**Fix:** Add composite indexes. See migration 004.

---

## 🟠 P1-3: Equity Chart Fetches 2000 Rows Every 30 Seconds

**Finding:** `useDashboardData` fetches up to 2000 `crypto_cash_snapshots` rows every 30s for the equity chart, even though the chart only needs to update when new data arrives.

**Impact:** Massive payload on mobile. ~200KB+ per poll cycle.

**Fix:**
1. Create `v_pnl_timeseries_daily` materialized view that pre-aggregates to 5-minute buckets
2. Add `last_snapshot_at` to health table so frontend can skip refetch if nothing changed
3. Long-term: SSE push from local event store

---

## 🟠 P1-4: No Reconciliation Table for Edge Factory

**Finding:** `SupabaseFeatureRepository` has no reconciliation mechanism. `SupabaseCryptoRepository` has `crypto_reconciliation_events` but Edge Factory has no equivalent. If Edge Factory restarts, it has no way to verify its position state matches broker reality.

**Fix:** Create `broker_reconciliation` table per spec. Edge Factory should reconcile on startup and periodically.

---

## 🟡 P2-1: No Config Versioning / Audit Trail

**Finding:** `config` table exists but is not used. Strategy parameters are set via env vars only. No audit trail when config changes.

**Impact:** Can't trace "which config was active when this trade was placed." Can't safely A/B test parameters.

**Fix:** Create `strategy_configs` and `config_audit_log` tables per Phase 4 spec.

---

## 🟡 P2-2: Duplicate candidate_scans Queries

**Finding:** The "latest batch" pattern (fetch latest created_at, then fetch all scans with that timestamp) is repeated in 5 different places:
- `useDashboardData.fetchPrices` (every 5s)
- `useDashboardData.fetchData` (every 30s)
- `Intelligence.fetchConsensus` (every 30s)
- `SupabaseCryptoRepository.latest_candidate_scans`
- `Charts.tsx` (in useEffect)

**Impact:** Same data fetched 3-4x per page view.

**Fix:** Create a Postgres function `get_latest_scan_batch(p_mode)` that does both queries server-side in one round trip. Frontend: share scan data via React context instead of independent fetches.

---

## 🟡 P2-3: No Stale Data Indicators in Dashboard

**Finding:** `healthSummary` only checks `crypto_reconciliation_events.taken_at` > 60s. No checks for stale candle data, stale scans, or stale quotes.

**Fix:** Create `zoe_health` table with `last_quote_ts`, `last_scan_ts`, `last_trade_ts`, `last_flush_ts`. Dashboard shows STALE banners when thresholds exceeded.

---

## 🟡 P2-4: thoughts.type Enum Mismatch

**Finding:** TypeScript types define `type: "scan" | "entry" | "exit" | "health" | "general"` but the frontend `TYPE_CONFIG` also handles `signal`, `paper_trade`, `order`, `order_error`. The actual data shows `scan` type in thoughts, and the backend `insert_thought` doesn't validate type.

**Impact:** No constraint enforcement. UI handles gracefully (falls back to `general`), but data integrity is weak.

**Fix:** Add CHECK constraint or use a reference table for thought types.

---

## 🟢 P3-1: zoe_events Table Exists But Is Not Populated

**Finding:** `zoe_events` is defined in types.ts with a proper event schema (source, subtype, severity, title, body, symbol) but no Python backend code writes to it. The unified event stream from Phase 1 could replace both `thoughts` and `audit_log`.

**Fix:** Phase 1 migration creates the unified `zoe_events` table. Backfill from existing `thoughts` records.

---

## 🟢 P3-2: No Pagination on List Queries

**Finding:** Most queries use `LIMIT` but no cursor-based pagination. `crypto_cash_snapshots` with `LIMIT 2000` is the worst offender.

**Fix:** Implement cursor pagination using `(mode, created_at)` or `(mode, id)` for all list endpoints. Mobile default LIMIT 50.

---

## 🟢 P3-3: Legacy Tables Can Be Archived

**Finding:** `positions`, `trades`, `daily_gameplans`, `daily_gameplan_items`, `crypto_tickers` appear unused.

**Fix:** Verify no external writers, then drop or archive.

---

## Migration Priority Order

1. **001_add_mode_to_ef_tables.sql** — P0-1 fix
2. **002_add_idempotency_and_trace.sql** — P0-3 fix
3. **003_create_health_and_reconcile.sql** — P1-4, P2-3 fixes
4. **004_indexes_and_views.sql** — P1-2, P1-3 fixes
5. **005_rls_policies.sql** — P0-2 fix
6. **006_config_versioning.sql** — P2-1 fix
7. **007_create_scan_batch_rpc.sql** — P2-2 fix

All migrations are additive and reversible (no column drops, no data deletions).
