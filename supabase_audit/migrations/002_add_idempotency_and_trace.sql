-- 002_add_idempotency_and_trace.sql
-- P0-3: Add idempotency keys and trace IDs for safe retries
-- Reversible: DROP columns

-- crypto_orders: idempotency key prevents duplicate order submission on restart
ALTER TABLE crypto_orders
  ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
  ADD COLUMN IF NOT EXISTS broker_order_id TEXT,
  ADD COLUMN IF NOT EXISTS trace_id TEXT;

-- Unique constraint on idempotency_key scoped to mode
CREATE UNIQUE INDEX IF NOT EXISTS idx_crypto_orders_idempotency
  ON crypto_orders (mode, idempotency_key)
  WHERE idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_crypto_orders_broker_id
  ON crypto_orders (mode, broker_order_id)
  WHERE broker_order_id IS NOT NULL;

-- crypto_fills: add trace_id for end-to-end tracing
ALTER TABLE crypto_fills
  ADD COLUMN IF NOT EXISTS trace_id TEXT;

-- ef_positions: add trace_id and idempotency
ALTER TABLE ef_positions
  ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
  ADD COLUMN IF NOT EXISTS trace_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_ef_positions_idempotency
  ON ef_positions (mode, idempotency_key)
  WHERE idempotency_key IS NOT NULL;
