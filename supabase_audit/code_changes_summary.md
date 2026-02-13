# Code Changes Summary

## Files to Change

### Backend (Python)

#### 1. `services/edge_factory/repository.py` — SupabaseFeatureRepository
**Change:** Add mode awareness to all methods
```python
class SupabaseFeatureRepository:
    def __init__(self, mode: str = "live") -> None:
        self.mode = mode
        # ... existing init ...

    def insert_feature(self, feature):
        self.client.table("ef_features").insert({
            "mode": self.mode,       # ← ADD
            # ... existing fields ...
        }).execute()

    def get_latest_feature(self, symbol, feature_name):
        resp = self.client.table("ef_features")
            .select("*")
            .eq("mode", self.mode)   # ← ADD
            .eq("symbol", symbol)
            # ...
```
Repeat for: `insert_regime`, `get_latest_regime`, `insert_signal`, `get_recent_signals`, `insert_position`, `update_position`, `get_open_positions`, `get_closed_positions`, `get_state`, `set_state`, `get_daily_notional`, `set_daily_notional`, `get_equity_high_water_mark`, `set_equity_high_water_mark`.

#### 2. `services/edge_factory/runner.py`
**Change:** Pass config mode to repository
```python
def _build_repository(config):
    if supabase_url and supabase_key:
        return SupabaseFeatureRepository(mode=config.mode)  # ← CHANGE
    return InMemoryFeatureRepository()
```

#### 3. `services/crypto_trader/supabase_repository.py`
**Changes:**
- `insert_order`: Generate and include `idempotency_key`
- `upsert_fill`: Add `trace_id` parameter
- New method: `update_health(mode, **fields)` → upsert to `zoe_health`

#### 4. `services/crypto_trader/trader.py`
**Changes:**
- After reconciliation: call `repo.update_health(mode, last_reconcile_ts=...)`
- After scan: call `repo.update_health(mode, last_scan_ts=...)`

### Frontend (TypeScript) — Future Optimization

#### 5. `zoe-terminal/src/hooks/useDashboardData.ts`
**Optimization (not blocking):**
- Replace 2-query scan pattern with `supabase.rpc('get_latest_scan_batch', { p_mode: mode })`
- Use `v_pnl_timeseries` view instead of raw `crypto_cash_snapshots` (drops from 2000 rows to ~250)
- Add Realtime subscription for `zoe_events` to reduce polling

#### 6. `zoe-terminal/src/lib/types.ts`
**Change:** Add new table types for `zoe_health`, `broker_reconciliation`, `strategy_configs`, `config_audit_log`

### New Files (Phase 6 — Local-First)

#### 7. `services/local_store.py` (NEW)
- SQLite connection manager with WAL mode
- `insert_event(event)` → write to local_events
- `get_unflushed(limit)` → SELECT unflushed events
- `mark_flushed(ids)` → UPDATE flushed = 1
- Sequence counter per mode

#### 8. `services/flush_worker.py` (NEW)
- Async flush loop with configurable intervals
- Batch upsert to Supabase `zoe_events`
- Immediate flush for critical event types
- Exponential backoff on failure
- Flush log writing

#### 9. `services/local_api.py` (NEW)
- FastAPI server on port 8765
- `GET /local/state` → current account state from SQLite
- `GET /local/events` → paginated event query
- `SSE /local/stream` → real-time event push
- Health endpoint for dashboard connectivity check

#### 10. `zoe-terminal/src/lib/localLive.ts` (NEW)
- `useLocalLive(mode)` hook
- SSE connection to local API
- Automatic fallback to Supabase
- Connection state badge

## Key Functions Changed

| File | Function | Change |
|------|----------|--------|
| `repository.py` | All SupabaseFeatureRepository methods | Add `.eq("mode", self.mode)` |
| `runner.py` | `_build_repository()` | Pass `config.mode` |
| `supabase_repository.py` | `insert_order()` | Add `idempotency_key` |
| `supabase_repository.py` | `upsert_fill()` | Add `trace_id` |
| `trader.py` | `_reconcile()` | Update `zoe_health` |

## Runbook: Enable Local-Live Mode

1. Install dependencies: `pip install aiosqlite fastapi uvicorn sse-starlette`
2. Create SQLite database: runs automatically on first boot
3. Set env vars:
   ```
   LOCAL_API_PORT=8765
   LOCAL_STORE_PATH=data/local_events.db
   FLUSH_INTERVAL_ACTIVE=15
   FLUSH_INTERVAL_OFFHOURS=120
   ```
4. Start local API: `python -m services.local_api`
5. Start flush worker: runs as part of the main trading loop
6. In frontend `.env`: `VITE_LOCAL_API_URL=http://localhost:8765`
7. Verify: Open dashboard → should show "LOCAL LIVE" badge
8. Debug: Check `data/local_events.db` with `sqlite3` CLI
