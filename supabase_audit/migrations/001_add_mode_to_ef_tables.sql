-- 001_add_mode_to_ef_tables.sql
-- P0-1: Add mode column to all Edge Factory tables for paper/live isolation
-- Reversible: ALTER TABLE ... DROP COLUMN mode;

-- ef_features
ALTER TABLE ef_features
  ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'live'
  CHECK (mode IN ('paper', 'live'));

CREATE INDEX IF NOT EXISTS idx_ef_features_mode_symbol_computed
  ON ef_features (mode, symbol, feature_name, computed_at DESC);

-- ef_regimes
ALTER TABLE ef_regimes
  ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'live'
  CHECK (mode IN ('paper', 'live'));

CREATE INDEX IF NOT EXISTS idx_ef_regimes_mode_detected
  ON ef_regimes (mode, detected_at DESC);

-- ef_signals
ALTER TABLE ef_signals
  ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'live'
  CHECK (mode IN ('paper', 'live'));

CREATE INDEX IF NOT EXISTS idx_ef_signals_mode_symbol_generated
  ON ef_signals (mode, symbol, generated_at DESC);

-- ef_positions
ALTER TABLE ef_positions
  ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'live'
  CHECK (mode IN ('paper', 'live'));

CREATE INDEX IF NOT EXISTS idx_ef_positions_mode_status
  ON ef_positions (mode, status);

-- ef_state
ALTER TABLE ef_state
  ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'live'
  CHECK (mode IN ('paper', 'live'));

-- ef_state: key was the primary lookup; now it needs (mode, key) uniqueness
-- First drop existing constraint if needed, then add composite
DO $$
BEGIN
  -- Only add if not already a composite key
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'ef_state' AND constraint_name = 'ef_state_mode_key_unique'
  ) THEN
    ALTER TABLE ef_state ADD CONSTRAINT ef_state_mode_key_unique UNIQUE (mode, key);
  END IF;
END $$;
