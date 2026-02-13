-- 005_rls_policies.sql
-- P0-2: Enable RLS — anon key read-only, service role full write
-- Reversible: ALTER TABLE ... DISABLE ROW LEVEL SECURITY; DROP POLICY ...;
--
-- STRATEGY: No Supabase Auth (users aren't authenticated in the traditional sense).
-- Instead we use a simple approach:
--   - Enable RLS on all tables
--   - Grant anon role SELECT only on dashboard-facing tables
--   - Service role (used by Python backend) bypasses RLS automatically
--   - No INSERT/UPDATE/DELETE for anon role on critical tables
--
-- The service_role key already bypasses RLS by default in Supabase.

-- ══════════════════════════════════════════════════
-- DASHBOARD READ-ONLY TABLES (anon can SELECT)
-- ══════════════════════════════════════════════════

-- Helper: enable RLS + create read-only policy for anon
DO $$
DECLARE
  tbl TEXT;
BEGIN
  FOR tbl IN VALUES
    ('candidate_scans'),
    ('crypto_cash_snapshots'),
    ('crypto_holdings_snapshots'),
    ('crypto_reconciliation_events'),
    ('crypto_orders'),
    ('crypto_fills'),
    ('crypto_candles'),
    ('daily_notional'),
    ('thoughts'),
    ('health_heartbeat'),
    ('pnl_daily'),
    ('market_pivots'),
    ('technical_trendlines'),
    ('technical_levels'),
    ('structure_events'),
    ('bounce_events'),
    ('bounce_intents'),
    ('zoe_events'),
    ('zoe_health'),
    ('config')
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);

    -- Drop existing policy if it exists (idempotent)
    EXECUTE format(
      'DROP POLICY IF EXISTS anon_read_%s ON %I',
      tbl, tbl
    );

    -- Allow anon to SELECT all rows
    EXECUTE format(
      'CREATE POLICY anon_read_%s ON %I FOR SELECT TO anon USING (true)',
      tbl, tbl
    );
  END LOOP;
END $$;

-- ══════════════════════════════════════════════════
-- COPILOT TABLES (anon can read + write own messages)
-- ══════════════════════════════════════════════════

ALTER TABLE copilot_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS anon_read_copilot ON copilot_messages;
CREATE POLICY anon_read_copilot ON copilot_messages
  FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS anon_insert_copilot ON copilot_messages;
CREATE POLICY anon_insert_copilot ON copilot_messages
  FOR INSERT TO anon WITH CHECK (true);

-- ══════════════════════════════════════════════════
-- BACKEND-ONLY TABLES (no anon access)
-- ══════════════════════════════════════════════════

DO $$
DECLARE
  tbl TEXT;
BEGIN
  FOR tbl IN VALUES
    ('ef_features'),
    ('ef_regimes'),
    ('ef_signals'),
    ('ef_positions'),
    ('ef_state'),
    ('agent_state'),
    ('boot_audit'),
    ('broker_reconciliation'),
    ('audit_log'),
    ('risk_events')
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);

    -- No policies for anon = no access (service_role bypasses RLS)
    -- Drop any existing permissive policies
    EXECUTE format(
      'DROP POLICY IF EXISTS anon_read_%s ON %I',
      tbl, tbl
    );
  END LOOP;
END $$;

-- ══════════════════════════════════════════════════
-- GRANT/REVOKE for extra safety
-- ══════════════════════════════════════════════════

-- Revoke all write permissions from anon on trading tables
DO $$
DECLARE
  tbl TEXT;
BEGIN
  FOR tbl IN VALUES
    ('crypto_orders'),
    ('crypto_fills'),
    ('crypto_cash_snapshots'),
    ('crypto_holdings_snapshots'),
    ('crypto_reconciliation_events'),
    ('daily_notional'),
    ('ef_features'),
    ('ef_regimes'),
    ('ef_signals'),
    ('ef_positions'),
    ('ef_state')
  LOOP
    EXECUTE format('REVOKE INSERT, UPDATE, DELETE ON %I FROM anon', tbl);
  END LOOP;
END $$;
