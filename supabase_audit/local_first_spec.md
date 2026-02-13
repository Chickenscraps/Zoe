# Phase 6 — Local-First Event Store + Batch Flush

## Architecture Overview

```
┌─────────────┐    SSE/WS     ┌──────────────┐     Batch Flush    ┌───────────┐
│  Dashboard   │ ◄──────────── │  Bot Machine │ ──────────────────► │  Supabase │
│  (browser)   │               │  (Python)    │    (15s / 120s)     │  (Postgres)│
│              │   local-live  │              │                     │            │
│  Falls back  │ ◄──────────── │  SQLite WAL  │                     │  System of │
│  to Supabase │               │  (events)    │                     │  Record    │
└─────────────┘               └──────────────┘                     └───────────┘
```

## A) SQLite Local Storage (on bot machine)

### Schema

```sql
-- local_events: mirror of zoe_events, unflushed events live here
CREATE TABLE local_events (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
  ts TEXT NOT NULL,           -- ISO8601
  seq INTEGER NOT NULL,
  source TEXT NOT NULL,
  type TEXT NOT NULL,
  subtype TEXT NOT NULL,
  symbol TEXT,
  severity TEXT NOT NULL DEFAULT 'info',
  body TEXT NOT NULL,
  meta_json TEXT DEFAULT '{}',
  idempotency_key TEXT UNIQUE,
  flushed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_local_events_unflushed ON local_events (flushed, seq ASC)
  WHERE flushed = 0;
CREATE INDEX idx_local_events_mode_seq ON local_events (mode, seq DESC);

-- local_flush_log: audit trail of flush operations
CREATE TABLE local_flush_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  mode TEXT NOT NULL,
  count INTEGER NOT NULL,
  last_seq INTEGER NOT NULL,
  status TEXT NOT NULL,   -- 'ok', 'partial', 'error'
  error TEXT
);

-- local_state_snapshots: periodic full state dumps for crash recovery
CREATE TABLE local_state_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT NOT NULL,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  state_json TEXT NOT NULL
);
```

### SQLite Settings
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA wal_autocheckpoint=1000")
```

## B) Local Live API (for dashboard on same LAN)

### Endpoints (FastAPI or similar lightweight server)

```
GET  /local/state?mode=live
  → { cash, holdings, positions, health, last_seq }

GET  /local/events?mode=live&since_seq=0&limit=50
  → [{ id, ts, seq, source, type, subtype, symbol, severity, body, meta }]

SSE  /local/stream?mode=live
  → Server-Sent Events, one JSON event per line
  → Reconnect with Last-Event-ID header (= last seq)
```

### Dashboard Behavior
```
1. Try connect to local endpoint (http://localhost:8765 or configured IP)
2. If reachable → use LOCAL LIVE as primary feed
3. If not reachable → fall back to Supabase reads/realtime
4. Show UI badge: "LOCAL LIVE" (green) vs "REMOTE" (amber)
5. Show "Supabase synced Xs ago" from zoe_health.last_flush_ts
```

## C) Flush Worker

### Config Dials
```python
FLUSH_INTERVAL_ACTIVE = 15      # seconds (during market hours)
FLUSH_INTERVAL_OFFHOURS = 120   # seconds (overnight/weekend)
FLUSH_BATCH_SIZE = 500           # max events per flush
FLUSH_CRITICAL_IMMEDIATE = True  # bypass timer for critical events
```

### Critical Event Types (flush immediately)
- `BUY_FILLED`
- `SELL_FILLED`
- `PNL_REALIZED`
- `TRADING_HALTED`
- `KILL_SWITCH`
- `RECONCILIATION_MISMATCH`

### Flush Logic (pseudocode)
```python
async def flush_loop():
    while True:
        interval = get_flush_interval()  # active vs offhours
        await asyncio.sleep(interval)
        await flush_batch()

async def flush_batch():
    # 1. Select unflushed events ordered by seq
    rows = db.execute("""
        SELECT * FROM local_events
        WHERE flushed = 0
        ORDER BY seq ASC
        LIMIT ?
    """, [FLUSH_BATCH_SIZE])

    if not rows:
        return

    # 2. Bulk upsert into Supabase zoe_events
    try:
        supabase.table("zoe_events").upsert(
            [row_to_dict(r) for r in rows],
            on_conflict="idempotency_key"
        ).execute()

        # 3. Mark as flushed
        ids = [r.id for r in rows]
        db.execute("""
            UPDATE local_events SET flushed = 1
            WHERE id IN ({})
        """.format(','.join(['?']*len(ids))), ids)

        # 4. Update health
        supabase.table("zoe_health").upsert({
            "mode": mode,
            "last_flush_ts": datetime.utcnow().isoformat(),
        }).execute()

        # 5. Log success
        db.execute("""
            INSERT INTO local_flush_log (mode, count, last_seq, status)
            VALUES (?, ?, ?, 'ok')
        """, [mode, len(rows), rows[-1].seq])

    except Exception as e:
        # Retry with exponential backoff; do NOT block trading loop
        db.execute("""
            INSERT INTO local_flush_log (mode, count, last_seq, status, error)
            VALUES (?, ?, ?, 'error', ?)
        """, [mode, len(rows), rows[-1].seq, str(e)])

async def on_critical_event(event):
    """Immediate flush for critical events."""
    if FLUSH_CRITICAL_IMMEDIATE and event.subtype in CRITICAL_TYPES:
        await flush_batch()
```

### Idempotency
- Every event gets a unique `idempotency_key` at creation time
- Supabase `zoe_events` has UNIQUE constraint on `idempotency_key`
- Repeated flush is safe — duplicates are ignored via ON CONFLICT
- Sequence (`seq`) is monotonic per mode; dashboard reconstructs order

### Crash Recovery
- On restart: scan `local_events WHERE flushed = 0` → flush to Supabase
- seq counter loaded from `MAX(seq)` in local_events for each mode
- State snapshots allow reconstruction without re-querying Supabase

## D) Dashboard Integration

### Frontend Changes
```typescript
// lib/localLive.ts
const LOCAL_API = import.meta.env.VITE_LOCAL_API_URL || 'http://localhost:8765';

export function useLocalLive(mode: TradingMode) {
  const [isLocal, setIsLocal] = useState(false);
  const [events, setEvents] = useState<ZoeEvent[]>([]);
  const [lastSeq, setLastSeq] = useState(0);

  useEffect(() => {
    // Try SSE connection to local API
    const evtSource = new EventSource(
      `${LOCAL_API}/local/stream?mode=${mode}`
    );

    evtSource.onopen = () => setIsLocal(true);
    evtSource.onerror = () => {
      setIsLocal(false);
      evtSource.close();
      // Fall back to Supabase polling
    };
    evtSource.onmessage = (e) => {
      const event = JSON.parse(e.data);
      setEvents(prev => [event, ...prev].slice(0, 200));
      setLastSeq(event.seq);
    };

    return () => evtSource.close();
  }, [mode]);

  return { isLocal, events, lastSeq };
}
```

### UI Badge
```
┌──────────────────────┐
│ ● LOCAL LIVE         │  ← green dot, connected to local SSE
│ Supabase synced 5s   │
└──────────────────────┘

┌──────────────────────┐
│ ○ REMOTE             │  ← amber dot, using Supabase directly
│ Polling every 30s    │
└──────────────────────┘
```

## Tests (mandatory)

1. **Crash simulation:** Write local event → kill process before flush → restart → verify it flushes correctly
2. **Duplicate flush:** Flush same batch twice → verify no duplicates in Supabase (idempotency_key)
3. **Ordering preserved:** Events arrive out-of-order → seq allows deterministic reconstruction
4. **Dashboard fallback:** Disconnect local API → dashboard switches to Supabase within 5s
5. **Critical immediate flush:** Insert BUY_FILLED event → verify it appears in Supabase within 2s
