-- 006_config_versioning.sql
-- P2-1: Strategy config versioning + audit trail
-- Reversible: DROP TABLE

CREATE TABLE IF NOT EXISTS strategy_configs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mode         TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
  version      INT NOT NULL,
  is_active    BOOLEAN NOT NULL DEFAULT false,
  config_json  JSONB NOT NULL,
  checksum     TEXT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by   TEXT NOT NULL DEFAULT 'system'
);

-- Only one active config per mode
CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_configs_active
  ON strategy_configs (mode) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_strategy_configs_mode_version
  ON strategy_configs (mode, version DESC);

-- Config change audit trail
CREATE TABLE IF NOT EXISTS config_audit_log (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mode       TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
  version    INT NOT NULL,
  diff_json  JSONB NOT NULL DEFAULT '{}',
  changed_by TEXT NOT NULL DEFAULT 'system',
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reason     TEXT
);

CREATE INDEX IF NOT EXISTS idx_config_audit_mode_version
  ON config_audit_log (mode, version DESC);

-- Enable RLS (backend-only)
ALTER TABLE strategy_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE config_audit_log ENABLE ROW LEVEL SECURITY;

-- Anon can read configs (for Settings page display)
CREATE POLICY anon_read_strategy_configs ON strategy_configs
  FOR SELECT TO anon USING (true);
CREATE POLICY anon_read_config_audit ON config_audit_log
  FOR SELECT TO anon USING (true);
