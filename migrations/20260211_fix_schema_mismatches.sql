-- 20260211_fix_schema_mismatches.sql
-- Fixes column name mismatches between Python code and SQL schema,
-- adds missing RLS policies, and forces a PostgREST schema cache reload.
--
-- Run in Supabase SQL Editor.

-- ---------------------------------------------------------
-- 1. FIX: crypto_holdings_snapshots.total_crypto_value
--    Python inserts "total_crypto_value" but table has "total_value"
-- ---------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'crypto_holdings_snapshots'
      AND column_name = 'total_crypto_value'
  ) THEN
    ALTER TABLE crypto_holdings_snapshots
      RENAME COLUMN total_value TO total_crypto_value;
  END IF;
END $$;

-- ---------------------------------------------------------
-- 2. FIX: daily_notional columns
--    Python uses "amount" but table has "notional_used"
-- ---------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'daily_notional'
      AND column_name = 'amount'
  ) THEN
    ALTER TABLE daily_notional
      RENAME COLUMN notional_used TO amount;
  END IF;
END $$;

-- ---------------------------------------------------------
-- 3. FIX: crypto_tickers.last_updated
--    Python uses "last_updated" but table has "updated_at"
-- ---------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'crypto_tickers'
      AND column_name = 'last_updated'
  ) THEN
    ALTER TABLE crypto_tickers
      RENAME COLUMN updated_at TO last_updated;
  END IF;
END $$;

-- ---------------------------------------------------------
-- 4. ADD MISSING RLS POLICIES
-- ---------------------------------------------------------
-- daily_notional: anon read + service_role write
DROP POLICY IF EXISTS "Public read notional" ON daily_notional;
CREATE POLICY "Public read notional" ON daily_notional
  FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "Service write notional" ON daily_notional;
CREATE POLICY "Service write notional" ON daily_notional
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- crypto_reconciliation_events: anon read + service_role write
DROP POLICY IF EXISTS "Public read reconciliation" ON crypto_reconciliation_events;
CREATE POLICY "Public read reconciliation" ON crypto_reconciliation_events
  FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "Service write reconciliation" ON crypto_reconciliation_events;
CREATE POLICY "Service write reconciliation" ON crypto_reconciliation_events
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ---------------------------------------------------------
-- 5. GRANT USAGE on public schema to anon + service_role
--    (ensures PostgREST can discover these tables)
-- ---------------------------------------------------------
GRANT USAGE ON SCHEMA public TO anon;
GRANT USAGE ON SCHEMA public TO service_role;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;

-- ---------------------------------------------------------
-- 6. FORCE PostgREST schema cache reload
-- ---------------------------------------------------------
NOTIFY pgrst, 'reload schema';
NOTIFY pgrst, 'reload config';
