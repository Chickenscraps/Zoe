-- Phase 4: Order Lifecycle — intents, events, trade locks
-- Run after 20260213_accounting_tables.sql

-- ============================================================
-- 1. Order intents — persistent, idempotent order tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS order_intents (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type      TEXT DEFAULT 'limit' CHECK (order_type IN ('limit', 'market')),
    qty             NUMERIC(20,8),
    notional        NUMERIC(20,8),
    limit_price     NUMERIC(20,8),
    engine          TEXT DEFAULT '',
    mode            TEXT DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    status          TEXT DEFAULT 'created' CHECK (status IN (
        'created', 'submitted', 'acked', 'partial_fill',
        'cancel_requested', 'cancelled', 'replaced',
        'filled', 'rejected', 'expired', 'error'
    )),
    broker_order_id TEXT,
    fill_price      NUMERIC(20,8),
    fill_qty        NUMERIC(20,8),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_intents_status
    ON order_intents (status) WHERE status NOT IN ('filled', 'cancelled', 'replaced', 'rejected', 'expired');

CREATE INDEX IF NOT EXISTS idx_order_intents_symbol_mode
    ON order_intents (symbol, mode);

CREATE INDEX IF NOT EXISTS idx_order_intents_created
    ON order_intents (created_at DESC);

-- ============================================================
-- 2. Order events — append-only audit trail
-- ============================================================
CREATE TABLE IF NOT EXISTS order_events (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    intent_id       UUID NOT NULL REFERENCES order_intents(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    broker_order_id TEXT,
    fill_price      NUMERIC(20,8),
    fill_qty        NUMERIC(20,8),
    fee             NUMERIC(20,8),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_events_intent
    ON order_events (intent_id, created_at);

-- ============================================================
-- 3. Trade locks — prevent concurrent engines on same symbol
-- ============================================================
CREATE TABLE IF NOT EXISTS trade_locks (
    symbol      TEXT NOT NULL,
    engine      TEXT NOT NULL,
    mode        TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    locked_at   TIMESTAMPTZ DEFAULT now(),
    lock_holder TEXT NOT NULL,
    PRIMARY KEY (symbol, engine, mode)
);

-- ============================================================
-- 4. RLS policies (anon read for dashboard)
-- ============================================================
ALTER TABLE order_intents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_order_intents" ON order_intents
    FOR SELECT USING (true);

ALTER TABLE order_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_order_events" ON order_events
    FOR SELECT USING (true);

ALTER TABLE trade_locks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_trade_locks" ON trade_locks
    FOR SELECT USING (true);

-- ============================================================
-- Notes:
-- - order_intents: idempotency_key prevents duplicate submissions
-- - order_events: append-only audit trail, FK cascade from intents
-- - trade_locks: PK on (symbol, engine, mode) for INSERT ON CONFLICT DO NOTHING pattern
-- - Partial index on status for fast active-intent queries
-- ============================================================
