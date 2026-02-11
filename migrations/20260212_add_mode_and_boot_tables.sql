-- Migration: Add mode column to all crypto tables + create boot reconciliation tables
-- Run this in the Supabase SQL Editor

BEGIN;

-- ============================================================
-- 1. Add `mode` column to all 10 crypto-related tables
-- ============================================================

-- crypto_orders
ALTER TABLE public.crypto_orders
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

-- crypto_fills
ALTER TABLE public.crypto_fills
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

-- crypto_cash_snapshots
ALTER TABLE public.crypto_cash_snapshots
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

-- crypto_holdings_snapshots
ALTER TABLE public.crypto_holdings_snapshots
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

-- crypto_reconciliation_events
ALTER TABLE public.crypto_reconciliation_events
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

-- daily_notional: drop old PK and recreate with mode
ALTER TABLE public.daily_notional
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

-- Drop old primary key (day only) and add new one including mode
ALTER TABLE public.daily_notional DROP CONSTRAINT IF EXISTS daily_notional_pkey;
ALTER TABLE public.daily_notional ADD PRIMARY KEY (day, mode);

-- pnl_daily: add mode, update unique constraint
ALTER TABLE public.pnl_daily
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

ALTER TABLE public.pnl_daily DROP CONSTRAINT IF EXISTS pnl_daily_pkey;
ALTER TABLE public.pnl_daily ADD PRIMARY KEY (date, instance_id, mode);

-- candidate_scans
ALTER TABLE public.candidate_scans
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

-- thoughts
ALTER TABLE public.thoughts
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

-- health_heartbeat: add mode, update unique constraint
ALTER TABLE public.health_heartbeat
  ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'paper'
  CHECK (mode IN ('paper', 'live'));

DROP INDEX IF EXISTS health_heartbeat_instance_component_idx;
CREATE UNIQUE INDEX health_heartbeat_instance_component_mode_idx
  ON public.health_heartbeat(instance_id, component, mode);

-- ============================================================
-- 2. Create agent_state table (boot reconciliation state snapshots)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.agent_state (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mode text NOT NULL CHECK (mode IN ('paper', 'live')),
  instance_id text NOT NULL DEFAULT 'default',
  state jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (mode, instance_id)
);

ALTER TABLE public.agent_state ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_read_agent_state" ON public.agent_state FOR SELECT USING (true);
CREATE POLICY "allow_service_all_agent_state" ON public.agent_state FOR ALL USING (true) WITH CHECK (true);
GRANT SELECT ON public.agent_state TO anon, authenticated;
GRANT ALL ON public.agent_state TO service_role;

-- ============================================================
-- 3. Create boot_audit table (boot reconciliation run records)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.boot_audit (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id text NOT NULL,
  mode text NOT NULL CHECK (mode IN ('paper', 'live')),
  instance_id text NOT NULL DEFAULT 'default',
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  duration_ms integer,
  status text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'ok', 'safe_mode', 'halted', 'error')),
  diffs jsonb DEFAULT '{}',
  integrity_checks jsonb DEFAULT '{}',
  resume_policy text,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.boot_audit ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_read_boot_audit" ON public.boot_audit FOR SELECT USING (true);
CREATE POLICY "allow_service_all_boot_audit" ON public.boot_audit FOR ALL USING (true) WITH CHECK (true);
GRANT SELECT ON public.boot_audit TO anon, authenticated;
GRANT ALL ON public.boot_audit TO service_role;

-- ============================================================
-- 4. Create indexes for mode-filtered queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_crypto_orders_mode ON public.crypto_orders(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_fills_mode ON public.crypto_fills(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_cash_snapshots_mode ON public.crypto_cash_snapshots(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_holdings_snapshots_mode ON public.crypto_holdings_snapshots(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_reconciliation_events_mode ON public.crypto_reconciliation_events(mode);
CREATE INDEX IF NOT EXISTS idx_candidate_scans_mode ON public.candidate_scans(mode);
CREATE INDEX IF NOT EXISTS idx_thoughts_mode ON public.thoughts(mode);
CREATE INDEX IF NOT EXISTS idx_pnl_daily_mode ON public.pnl_daily(mode);

COMMIT;

-- Reload PostgREST schema cache
NOTIFY pgrst, 'reload schema';
