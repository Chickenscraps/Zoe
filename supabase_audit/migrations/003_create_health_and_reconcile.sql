-- 003_create_health_and_reconcile.sql
-- P1-4, P2-3: Health signals table + broker reconciliation for Edge Factory
-- Reversible: DROP TABLE

-- Unified health dashboard — replaces scattered status checks
CREATE TABLE IF NOT EXISTS zoe_health (
  mode       TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
  last_quote_ts   TIMESTAMPTZ,
  last_scan_ts    TIMESTAMPTZ,
  last_trade_ts   TIMESTAMPTZ,
  last_flush_ts   TIMESTAMPTZ,
  last_reconcile_ts TIMESTAMPTZ,
  status     TEXT NOT NULL DEFAULT 'unknown'
    CHECK (status IN ('healthy', 'degraded', 'stale', 'offline', 'unknown')),
  warning_count  INT NOT NULL DEFAULT 0,
  error_count    INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (mode)
);

-- Broker reconciliation snapshots for Edge Factory
CREATE TABLE IF NOT EXISTS broker_reconciliation (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  mode      TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
  status    TEXT NOT NULL CHECK (status IN ('ok', 'mismatch', 'error')),
  summary   JSONB NOT NULL DEFAULT '{}',
  mismatches JSONB DEFAULT '{}',
  broker_positions JSONB DEFAULT '{}',
  local_positions  JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_broker_reconciliation_mode_ts
  ON broker_reconciliation (mode, ts DESC);

-- Unified event stream (enhances existing zoe_events table if it exists)
-- This becomes the single source of truth for all system events
CREATE TABLE IF NOT EXISTS zoe_events (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  mode            TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
  seq             BIGINT NOT NULL,
  source          TEXT NOT NULL,
  type            TEXT NOT NULL,
  subtype         TEXT NOT NULL,
  symbol          TEXT,
  severity        TEXT NOT NULL DEFAULT 'info'
    CHECK (severity IN ('info', 'good', 'bad', 'warn', 'neutral')),
  body            TEXT NOT NULL,
  meta            JSONB DEFAULT '{}',
  trace_id        TEXT,
  config_version  INT,
  idempotency_key TEXT UNIQUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Monotonic sequence per mode
CREATE SEQUENCE IF NOT EXISTS zoe_events_seq_paper;
CREATE SEQUENCE IF NOT EXISTS zoe_events_seq_live;

CREATE INDEX IF NOT EXISTS idx_zoe_events_mode_ts
  ON zoe_events (mode, ts DESC);
CREATE INDEX IF NOT EXISTS idx_zoe_events_mode_seq
  ON zoe_events (mode, seq DESC);
CREATE INDEX IF NOT EXISTS idx_zoe_events_mode_symbol_ts
  ON zoe_events (mode, symbol, ts DESC);
