-- 20260211_full_setup.sql
-- COMPLETE setup: tables + column names matching Python code + RLS + grants + cache reload
-- Run this on the CORRECT Supabase project (qwdkadwuyejyadwptgfd)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================================
-- 1. TABLES (with column names matching Python code exactly)
-- ==========================================================

CREATE TABLE IF NOT EXISTS crypto_orders (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_order_id text UNIQUE NOT NULL,
    symbol text NOT NULL,
    side text NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type text NOT NULL DEFAULT 'market',
    qty numeric,
    notional numeric,
    limit_price numeric,
    status text NOT NULL DEFAULT 'pending',
    filled_qty numeric DEFAULT 0,
    filled_avg_price numeric DEFAULT 0,
    fees numeric DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    raw_response jsonb
);

CREATE TABLE IF NOT EXISTS crypto_cash_snapshots (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    cash_available numeric NOT NULL,
    buying_power numeric NOT NULL,
    taken_at timestamptz DEFAULT now()
);

-- NOTE: column is "total_crypto_value" to match Python code
CREATE TABLE IF NOT EXISTS crypto_holdings_snapshots (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    holdings jsonb NOT NULL,
    total_crypto_value numeric NOT NULL DEFAULT 0,
    taken_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crypto_candles (
    symbol text NOT NULL,
    timeframe text NOT NULL,
    bucket timestamptz NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric DEFAULT 0,
    is_final boolean DEFAULT false,
    PRIMARY KEY (symbol, timeframe, bucket)
);

-- NOTE: column is "last_updated" to match Python code
CREATE TABLE IF NOT EXISTS crypto_tickers (
    symbol text PRIMARY KEY,
    price numeric NOT NULL,
    last_updated timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crypto_audit_log (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp timestamptz DEFAULT now(),
    component text NOT NULL,
    event text NOT NULL,
    level text DEFAULT 'info',
    details jsonb
);

CREATE TABLE IF NOT EXISTS crypto_reconciliation_events (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    status text NOT NULL,
    reason text,
    taken_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS daily_gameplans (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    date date UNIQUE NOT NULL,
    status text DEFAULT 'draft',
    instance_id text,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS daily_gameplan_items (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id uuid REFERENCES daily_gameplans(id) ON DELETE CASCADE,
    symbol text NOT NULL,
    catalyst_summary text,
    regime text,
    ivr_tech_snapshot text,
    preferred_strategy text,
    risk_tier text,
    created_at timestamptz DEFAULT now()
);

-- NOTE: column is "amount" to match Python code
CREATE TABLE IF NOT EXISTS daily_notional (
    day date PRIMARY KEY DEFAULT current_date,
    amount numeric DEFAULT 0,
    last_updated timestamptz DEFAULT now()
);

-- ==========================================================
-- 2. ENABLE RLS
-- ==========================================================

ALTER TABLE crypto_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE crypto_cash_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE crypto_holdings_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE crypto_candles ENABLE ROW LEVEL SECURITY;
ALTER TABLE crypto_tickers ENABLE ROW LEVEL SECURITY;
ALTER TABLE crypto_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE crypto_reconciliation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_gameplans ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_gameplan_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_notional ENABLE ROW LEVEL SECURITY;

-- ==========================================================
-- 3. RLS POLICIES (drop first to avoid conflicts)
-- ==========================================================

-- anon SELECT (dashboard reads)
DROP POLICY IF EXISTS "anon_read" ON crypto_orders;
DROP POLICY IF EXISTS "anon_read" ON crypto_cash_snapshots;
DROP POLICY IF EXISTS "anon_read" ON crypto_holdings_snapshots;
DROP POLICY IF EXISTS "anon_read" ON crypto_candles;
DROP POLICY IF EXISTS "anon_read" ON crypto_tickers;
DROP POLICY IF EXISTS "anon_read" ON crypto_audit_log;
DROP POLICY IF EXISTS "anon_read" ON crypto_reconciliation_events;
DROP POLICY IF EXISTS "anon_read" ON daily_gameplans;
DROP POLICY IF EXISTS "anon_read" ON daily_gameplan_items;
DROP POLICY IF EXISTS "anon_read" ON daily_notional;

CREATE POLICY "anon_read" ON crypto_orders FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON crypto_cash_snapshots FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON crypto_holdings_snapshots FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON crypto_candles FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON crypto_tickers FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON crypto_audit_log FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON crypto_reconciliation_events FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON daily_gameplans FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON daily_gameplan_items FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON daily_notional FOR SELECT TO anon USING (true);

-- service_role ALL (bot writes)
DROP POLICY IF EXISTS "service_all" ON crypto_orders;
DROP POLICY IF EXISTS "service_all" ON crypto_cash_snapshots;
DROP POLICY IF EXISTS "service_all" ON crypto_holdings_snapshots;
DROP POLICY IF EXISTS "service_all" ON crypto_candles;
DROP POLICY IF EXISTS "service_all" ON crypto_tickers;
DROP POLICY IF EXISTS "service_all" ON crypto_audit_log;
DROP POLICY IF EXISTS "service_all" ON crypto_reconciliation_events;
DROP POLICY IF EXISTS "service_all" ON daily_gameplans;
DROP POLICY IF EXISTS "service_all" ON daily_gameplan_items;
DROP POLICY IF EXISTS "service_all" ON daily_notional;

CREATE POLICY "service_all" ON crypto_orders FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON crypto_cash_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON crypto_holdings_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON crypto_candles FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON crypto_tickers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON crypto_audit_log FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON crypto_reconciliation_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON daily_gameplans FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON daily_gameplan_items FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON daily_notional FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ==========================================================
-- 4. GRANTS (ensure PostgREST can discover + access tables)
-- ==========================================================

GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO postgres, anon, authenticated, service_role;

-- ==========================================================
-- 5. FORCE PostgREST CACHE RELOAD
-- ==========================================================

NOTIFY pgrst, 'reload schema';
NOTIFY pgrst, 'reload config';
