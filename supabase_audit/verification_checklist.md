# Verification Checklist & Smoke Tests

## Pre-Migration Checks
- [ ] Backup all Supabase tables (pg_dump or Supabase dashboard export)
- [ ] Note current row counts for all tables
- [ ] Verify service_role key is available for migration execution
- [ ] Verify Edge Factory is stopped before running 001

## Migration Execution Order
Run in Supabase SQL Editor (or via CLI: `supabase db push`):

1. [ ] `001_add_mode_to_ef_tables.sql` — adds mode column to ef_* tables
2. [ ] `002_add_idempotency_and_trace.sql` — adds idempotency_key, broker_order_id, trace_id
3. [ ] `003_create_health_and_reconcile.sql` — creates zoe_health, broker_reconciliation, zoe_events
4. [ ] `004_indexes_and_views.sql` — creates all performance indexes + compact views
5. [ ] `005_rls_policies.sql` — enables RLS on all tables
6. [ ] `006_config_versioning.sql` — creates strategy_configs + audit log
7. [ ] `007_create_scan_batch_rpc.sql` — creates get_latest_scan_batch() function

## Post-Migration Smoke Tests

### 001 Verification: ef_* mode column
```sql
-- Verify all ef_* tables have mode column
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name LIKE 'ef_%' AND column_name = 'mode';
-- Expected: 5 rows (ef_features, ef_regimes, ef_signals, ef_positions, ef_state)

-- Verify existing data got default 'live'
SELECT mode, COUNT(*) FROM ef_features GROUP BY mode;
SELECT mode, COUNT(*) FROM ef_positions GROUP BY mode;
```

### 002 Verification: Idempotency keys
```sql
-- Verify new columns exist
SELECT column_name FROM information_schema.columns
WHERE table_name = 'crypto_orders' AND column_name IN ('idempotency_key', 'broker_order_id', 'trace_id');
-- Expected: 3 rows

-- Verify unique index works
INSERT INTO crypto_orders (id, client_order_id, symbol, side, order_type, status, requested_at, mode, idempotency_key)
VALUES (gen_random_uuid(), 'test', 'BTC-USD', 'buy', 'market', 'new', NOW(), 'live', 'test-key-1');
-- Should succeed

INSERT INTO crypto_orders (id, client_order_id, symbol, side, order_type, status, requested_at, mode, idempotency_key)
VALUES (gen_random_uuid(), 'test2', 'BTC-USD', 'buy', 'market', 'new', NOW(), 'live', 'test-key-1');
-- Should FAIL with unique constraint violation

-- Cleanup
DELETE FROM crypto_orders WHERE idempotency_key = 'test-key-1';
```

### 003 Verification: zoe_health + zoe_events
```sql
-- Insert test health record
INSERT INTO zoe_health (mode, status) VALUES ('live', 'healthy')
ON CONFLICT (mode) DO UPDATE SET status = 'healthy', updated_at = NOW();
SELECT * FROM zoe_health;

-- Insert test event
INSERT INTO zoe_events (mode, seq, source, type, subtype, body, idempotency_key)
VALUES ('live', 1, 'test', 'SYSTEM', 'TEST', 'Smoke test event', 'smoke-test-1');
SELECT * FROM zoe_events WHERE idempotency_key = 'smoke-test-1';

-- Verify duplicate rejected
INSERT INTO zoe_events (mode, seq, source, type, subtype, body, idempotency_key)
VALUES ('live', 2, 'test', 'SYSTEM', 'TEST', 'Duplicate', 'smoke-test-1')
ON CONFLICT (idempotency_key) DO NOTHING;
SELECT COUNT(*) FROM zoe_events WHERE source = 'test';
-- Expected: 1

-- Cleanup
DELETE FROM zoe_events WHERE source = 'test';
```

### 004 Verification: Indexes + Views
```sql
-- Verify indexes were created
SELECT indexname FROM pg_indexes WHERE tablename = 'candidate_scans';
-- Should include idx_candidate_scans_mode_created

-- Test v_scanner_latest view
SELECT * FROM v_scanner_latest WHERE mode = 'live' LIMIT 5;
-- Should return latest batch of scans

-- Test v_pnl_timeseries view
SELECT * FROM v_pnl_timeseries WHERE mode = 'live' LIMIT 10;
-- Should return bucketed equity points

-- Verify index is being used (EXPLAIN)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM candidate_scans
WHERE mode = 'live'
ORDER BY created_at DESC
LIMIT 10;
-- Should show Index Scan, not Seq Scan
```

### 005 Verification: RLS
```sql
-- Test from anon role context
SET ROLE anon;

-- Should work (read-only on dashboard tables)
SELECT COUNT(*) FROM candidate_scans;
SELECT COUNT(*) FROM thoughts;

-- Should FAIL (no write access)
INSERT INTO crypto_orders (id, client_order_id, symbol, side, order_type, status, requested_at, mode)
VALUES (gen_random_uuid(), 'hack', 'BTC-USD', 'buy', 'market', 'new', NOW(), 'live');
-- Expected: permission denied

-- Should FAIL (no access to backend tables)
SELECT * FROM ef_features;
-- Expected: 0 rows (RLS blocks all)

-- Reset role
RESET ROLE;
```

### 007 Verification: RPC Function
```sql
-- Test the scan batch function
SELECT * FROM get_latest_scan_batch('live') LIMIT 5;
-- Should return same results as the 2-query pattern
```

## Backend Code Updates Required

After migrations, update these Python files:

### SupabaseFeatureRepository (edge_factory/repository.py)
- [ ] Pass `mode` to all queries: `.eq("mode", self.mode)`
- [ ] Add `self.mode` attribute (from config)
- [ ] Update `insert_feature`, `get_latest_feature`, `get_feature_history`
- [ ] Update `insert_regime`, `get_latest_regime`
- [ ] Update `insert_signal`, `get_recent_signals`
- [ ] Update `insert_position`, `update_position`, `get_open_positions`, `get_closed_positions`
- [ ] Update `get_state`, `set_state` to include mode

### SupabaseCryptoRepository (crypto_trader/supabase_repository.py)
- [ ] Add `idempotency_key` to `insert_order`
- [ ] Add `trace_id` to `upsert_fill`
- [ ] Write to `zoe_health` on each reconciliation cycle

### Frontend (optional, future)
- [ ] Replace 5s price polling with Supabase Realtime on candidate_scans
- [ ] Use `get_latest_scan_batch` RPC instead of 2-query pattern
- [ ] Use `v_pnl_timeseries` view instead of fetching 2000 raw snapshots

## Rollback Plan

Each migration is independently reversible:
```sql
-- 001: ALTER TABLE ef_features DROP COLUMN mode; (repeat for each ef_* table)
-- 002: ALTER TABLE crypto_orders DROP COLUMN idempotency_key, DROP COLUMN broker_order_id, DROP COLUMN trace_id;
-- 003: DROP TABLE zoe_health; DROP TABLE broker_reconciliation;
-- 004: DROP INDEX idx_candidate_scans_mode_created; ... (drop each index)
-- 005: ALTER TABLE candidate_scans DISABLE ROW LEVEL SECURITY; ... (repeat for each table)
-- 006: DROP TABLE strategy_configs; DROP TABLE config_audit_log;
-- 007: DROP FUNCTION get_latest_scan_batch;
```
