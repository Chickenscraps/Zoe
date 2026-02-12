-- ============================================================
-- Strategy Configs + Config Audit Log
-- Versioned, mode-scoped trading configuration ("Dials")
-- ============================================================

-- 1) strategy_configs — one active config per mode at a time
CREATE TABLE IF NOT EXISTS strategy_configs (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    mode        text NOT NULL CHECK (mode IN ('paper', 'live')),
    name        text NOT NULL DEFAULT 'default',
    config_json jsonb NOT NULL,
    version     int NOT NULL DEFAULT 1,
    is_active   boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  text NOT NULL DEFAULT 'system',
    checksum    text NOT NULL
);

-- Enforce: at most one active config per mode
CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_configs_active_mode
    ON strategy_configs (mode) WHERE (is_active = true);

-- Fast lookup by mode + version
CREATE INDEX IF NOT EXISTS idx_strategy_configs_mode_version
    ON strategy_configs (mode, version DESC);

-- 2) config_audit_log — every change is recorded
CREATE TABLE IF NOT EXISTS config_audit_log (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    mode        text NOT NULL CHECK (mode IN ('paper', 'live')),
    version     int NOT NULL,
    changed_at  timestamptz NOT NULL DEFAULT now(),
    changed_by  text NOT NULL DEFAULT 'system',
    diff_json   jsonb NOT NULL DEFAULT '{}',
    reason      text,
    prev_config jsonb,
    new_config  jsonb
);

CREATE INDEX IF NOT EXISTS idx_config_audit_log_mode
    ON config_audit_log (mode, changed_at DESC);

-- 3) RLS policies (permissive for service role, read for anon)
ALTER TABLE strategy_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE config_audit_log ENABLE ROW LEVEL SECURITY;

-- Allow anon key to read configs (dashboard reads)
CREATE POLICY IF NOT EXISTS "anon_read_strategy_configs"
    ON strategy_configs FOR SELECT
    USING (true);

CREATE POLICY IF NOT EXISTS "anon_read_config_audit_log"
    ON config_audit_log FOR SELECT
    USING (true);

-- Allow service role full access
CREATE POLICY IF NOT EXISTS "service_all_strategy_configs"
    ON strategy_configs FOR ALL
    USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "service_all_config_audit_log"
    ON config_audit_log FOR ALL
    USING (true) WITH CHECK (true);

-- 4) Add config_version and config_checksum to crypto_orders if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'crypto_orders' AND column_name = 'config_version'
    ) THEN
        ALTER TABLE crypto_orders ADD COLUMN config_version int;
        ALTER TABLE crypto_orders ADD COLUMN config_checksum text;
    END IF;
END $$;

-- 5) Add config_version and config_checksum to crypto_fills if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'crypto_fills' AND column_name = 'config_version'
    ) THEN
        ALTER TABLE crypto_fills ADD COLUMN config_version int;
        ALTER TABLE crypto_fills ADD COLUMN config_checksum text;
    END IF;
END $$;

-- 6) Add config_version to ef_positions (edge factory positions)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ef_positions' AND column_name = 'config_version'
    ) THEN
        ALTER TABLE ef_positions ADD COLUMN config_version int;
        ALTER TABLE ef_positions ADD COLUMN config_checksum text;
    END IF;
END $$;
