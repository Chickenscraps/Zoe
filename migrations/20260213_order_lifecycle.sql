-- Order Lifecycle: intent tracking, event log, repositioning columns, trade locks
-- Depends on: crypto_orders table existing

-- ── Extend crypto_orders for repositioning ──
ALTER TABLE crypto_orders ADD COLUMN IF NOT EXISTS intent_group_id UUID;
ALTER TABLE crypto_orders ADD COLUMN IF NOT EXISTS replace_count INT DEFAULT 0;
ALTER TABLE crypto_orders ADD COLUMN IF NOT EXISTS cancel_reason_code TEXT;
ALTER TABLE crypto_orders ADD COLUMN IF NOT EXISTS remaining_qty NUMERIC;
ALTER TABLE crypto_orders ADD COLUMN IF NOT EXISTS ttl_seconds INT;
ALTER TABLE crypto_orders ADD COLUMN IF NOT EXISTS next_action_at TIMESTAMPTZ;
ALTER TABLE crypto_orders ADD COLUMN IF NOT EXISTS parent_order_id UUID;
ALTER TABLE crypto_orders ADD COLUMN IF NOT EXISTS limit_price NUMERIC;

CREATE INDEX IF NOT EXISTS idx_orders_intent_group ON crypto_orders(intent_group_id);

-- ── Order events: append-only transition log ──
CREATE TABLE IF NOT EXISTS order_events (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  order_id UUID NOT NULL,
  intent_group_id UUID,
  event_type TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT NOT NULL,
  limit_price NUMERIC,
  filled_qty NUMERIC,
  filled_price NUMERIC,
  reason TEXT,
  metadata JSONB DEFAULT '{}',
  trace_id TEXT,
  mode TEXT NOT NULL DEFAULT 'paper',
  ts TIMESTAMPTZ DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_events_order ON order_events(order_id, ts);
CREATE INDEX IF NOT EXISTS idx_order_events_intent ON order_events(intent_group_id, ts);
ALTER TABLE order_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_read_order_events" ON order_events FOR SELECT USING (true);
CREATE POLICY "allow_service_order_events" ON order_events FOR ALL USING (true) WITH CHECK (true);

-- ── Order intents: "why" behind an order chain ──
CREATE TABLE IF NOT EXISTS order_intents (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
  purpose TEXT NOT NULL DEFAULT 'entry' CHECK (purpose IN ('entry', 'exit', 'flatten')),
  target_notional NUMERIC NOT NULL,
  signal_confidence NUMERIC,
  strategy TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  max_reprices INT DEFAULT 3,
  reprice_step_bps NUMERIC DEFAULT 5.0,
  ttl_per_attempt_sec INT DEFAULT 60,
  mode TEXT NOT NULL DEFAULT 'paper',
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  trace_id TEXT
);
ALTER TABLE order_intents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_read_order_intents" ON order_intents FOR SELECT USING (true);
CREATE POLICY "allow_service_order_intents" ON order_intents FOR ALL USING (true) WITH CHECK (true);

-- ── Trade locks: prevent dual-engine symbol collisions ──
CREATE TABLE IF NOT EXISTS trade_locks (
  symbol TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
  engine TEXT NOT NULL,
  locked_at TIMESTAMPTZ DEFAULT now(),
  ttl_seconds INT DEFAULT 300,
  instance_id TEXT NOT NULL DEFAULT 'default',
  PRIMARY KEY (symbol, mode)
);
ALTER TABLE trade_locks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_read_trade_locks" ON trade_locks FOR SELECT USING (true);
CREATE POLICY "allow_service_trade_locks" ON trade_locks FOR ALL USING (true) WITH CHECK (true);
