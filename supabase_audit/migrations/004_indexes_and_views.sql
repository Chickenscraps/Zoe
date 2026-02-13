-- 004_indexes_and_views.sql
-- P1-2, P1-3: Critical indexes + compact views for mobile performance
-- Reversible: DROP INDEX / DROP VIEW

-- ══════════════════════════════════════════════════
-- CRITICAL INDEXES (ordered by query frequency)
-- ══════════════════════════════════════════════════

-- candidate_scans: hit every 5s for price polling + every 30s for dashboard
CREATE INDEX IF NOT EXISTS idx_candidate_scans_mode_created
  ON candidate_scans (mode, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidate_scans_mode_symbol_created
  ON candidate_scans (mode, symbol, created_at DESC);

-- crypto_cash_snapshots: 2000 rows fetched for equity chart
CREATE INDEX IF NOT EXISTS idx_crypto_cash_mode_taken
  ON crypto_cash_snapshots (mode, taken_at DESC);

CREATE INDEX IF NOT EXISTS idx_crypto_cash_mode_taken_asc
  ON crypto_cash_snapshots (mode, taken_at ASC);

-- thoughts: polled every 15s
CREATE INDEX IF NOT EXISTS idx_thoughts_mode_created
  ON thoughts (mode, created_at DESC);

-- crypto_candles: per symbol+timeframe queries
CREATE INDEX IF NOT EXISTS idx_crypto_candles_lookup
  ON crypto_candles (symbol, timeframe, mode, open_time ASC);

-- crypto_fills: used for P&L calculation
CREATE INDEX IF NOT EXISTS idx_crypto_fills_mode_executed
  ON crypto_fills (mode, executed_at DESC);

-- crypto_orders: filtered by status
CREATE INDEX IF NOT EXISTS idx_crypto_orders_mode_status
  ON crypto_orders (mode, status, requested_at DESC);

-- crypto_holdings_snapshots: latest by mode
CREATE INDEX IF NOT EXISTS idx_crypto_holdings_mode_taken
  ON crypto_holdings_snapshots (mode, taken_at DESC);

-- crypto_reconciliation_events: health check
CREATE INDEX IF NOT EXISTS idx_crypto_reconcile_mode_taken
  ON crypto_reconciliation_events (mode, taken_at DESC);

-- Structure tables
CREATE INDEX IF NOT EXISTS idx_market_pivots_mode_ts
  ON market_pivots (mode, "timestamp" DESC);

CREATE INDEX IF NOT EXISTS idx_technical_trendlines_mode_active
  ON technical_trendlines (mode, is_active, score DESC)
  WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_technical_levels_mode_active
  ON technical_levels (mode, is_active, score DESC)
  WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_structure_events_mode_ts
  ON structure_events (mode, ts DESC);

CREATE INDEX IF NOT EXISTS idx_bounce_events_mode_ts
  ON bounce_events (mode, ts DESC);

CREATE INDEX IF NOT EXISTS idx_bounce_intents_mode_ts
  ON bounce_intents (mode, ts DESC);

-- pnl_daily: equity chart fallback
CREATE INDEX IF NOT EXISTS idx_pnl_daily_mode_date
  ON pnl_daily (mode, date ASC);

-- health_heartbeat
CREATE INDEX IF NOT EXISTS idx_health_heartbeat_mode
  ON health_heartbeat (mode, instance_id, component);

-- ══════════════════════════════════════════════════
-- COMPACT VIEWS FOR MOBILE
-- ══════════════════════════════════════════════════

-- v_positions_compact: only fields needed for dashboard position cards
CREATE OR REPLACE VIEW v_positions_compact AS
SELECT
  h.mode,
  h.taken_at,
  h.holdings,
  h.total_crypto_value
FROM crypto_holdings_snapshots h
INNER JOIN (
  SELECT mode, MAX(taken_at) AS max_taken
  FROM crypto_holdings_snapshots
  GROUP BY mode
) latest ON h.mode = latest.mode AND h.taken_at = latest.max_taken;

-- v_scanner_latest: latest scan per symbol (avoids the 2-query pattern)
CREATE OR REPLACE VIEW v_scanner_latest AS
SELECT cs.*
FROM candidate_scans cs
INNER JOIN (
  SELECT mode, MAX(created_at) AS max_created
  FROM candidate_scans
  GROUP BY mode
) latest ON cs.mode = latest.mode AND cs.created_at = latest.max_created;

-- v_pnl_timeseries: aggregated equity points for chart (5-min buckets)
CREATE OR REPLACE VIEW v_pnl_timeseries AS
SELECT
  mode,
  date_trunc('hour', taken_at) +
    (EXTRACT(minute FROM taken_at)::int / 5) * INTERVAL '5 minutes' AS bucket,
  MAX(buying_power) AS buying_power,
  MAX(cash_available) AS cash_available,
  MAX(taken_at) AS latest_at
FROM crypto_cash_snapshots
WHERE taken_at > NOW() - INTERVAL '90 days'
GROUP BY mode, bucket
ORDER BY mode, bucket;
