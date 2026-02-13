# Phase 5 — Realtime Subscription Plan

## Current State
All data is fetched via polling (30s dashboard, 5s prices, 15s thoughts). Zero Realtime subscriptions.

## Recommended Subscriptions

### Primary: zoe_events (read-only)
```typescript
supabase
  .channel('zoe-events')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'zoe_events',
    filter: `mode=eq.${mode}`,
  }, handleNewEvent)
  .subscribe();
```
**Purpose:** Single event stream that notifies the dashboard of all system activity. Frontend can update local state from event metadata instead of re-polling.

### Secondary: zoe_health
```typescript
supabase
  .channel('zoe-health')
  .on('postgres_changes', {
    event: '*',
    schema: 'public',
    table: 'zoe_health',
    filter: `mode=eq.${mode}`,
  }, handleHealthUpdate)
  .subscribe();
```
**Purpose:** Instant status badge updates (LIVE/DEGRADED/STALE).

### Optional: candidate_scans (replace 5s price polling)
```typescript
supabase
  .channel('scanner')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'candidate_scans',
    filter: `mode=eq.${mode}`,
  }, handleNewScan)
  .subscribe();
```
**Purpose:** Replace 5s price polling interval. Scanner inserts new batch → frontend updates immediately.

## Rules
- Client NEVER writes through Realtime
- All subscriptions are mode-filtered
- Fallback to polling if WebSocket disconnects (exponential backoff)
- Max 3 active subscriptions per client

## Impact
- Eliminates ~36 polling queries/min (dashboard + price + thoughts)
- Reduces to ~10 queries/min (initial load + structure data which changes infrequently)
- ~70% reduction in Supabase query volume
