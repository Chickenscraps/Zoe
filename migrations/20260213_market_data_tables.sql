-- Phase 2: Market Catalog + Adaptive Market Watch tables
-- Run against Supabase Postgres

-- ═══════════════════════════════════════════════════════════════
-- 1. market_catalog — discovered from Kraken AssetPairs at startup
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS market_catalog (
    symbol          TEXT PRIMARY KEY,          -- Internal: "BTC-USD"
    exchange_symbol TEXT NOT NULL,             -- Kraken REST: "XXBTZUSD"
    ws_symbol       TEXT,                      -- Kraken WS v2: "BTC/USD"
    base            TEXT NOT NULL,             -- "BTC"
    quote           TEXT NOT NULL DEFAULT 'USD',
    exchange        TEXT NOT NULL DEFAULT 'kraken',
    status          TEXT NOT NULL DEFAULT 'active',  -- active | delisted | halted
    min_qty         NUMERIC(20,10) DEFAULT 0,
    lot_size        NUMERIC(20,10) DEFAULT 0,
    tick_size       NUMERIC(20,10) DEFAULT 0,
    fee_maker_pct   NUMERIC(8,4) DEFAULT 0.16,  -- Kraken intermediate tier
    fee_taker_pct   NUMERIC(8,4) DEFAULT 0.26,
    ordermin        NUMERIC(20,10) DEFAULT 0,    -- Kraken min order size
    metadata        JSONB DEFAULT '{}',
    discovered_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_catalog_base ON market_catalog(base);
CREATE INDEX IF NOT EXISTS idx_market_catalog_status ON market_catalog(status);
CREATE INDEX IF NOT EXISTS idx_market_catalog_updated ON market_catalog(updated_at);


-- ═══════════════════════════════════════════════════════════════
-- 2. market_snapshot_focus — live prices for focus universe (1s flush)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS market_snapshot_focus (
    symbol          TEXT PRIMARY KEY,
    bid             NUMERIC(20,8) NOT NULL DEFAULT 0,
    ask             NUMERIC(20,8) NOT NULL DEFAULT 0,
    mid             NUMERIC(20,8) NOT NULL DEFAULT 0,
    spread_pct      NUMERIC(10,6) DEFAULT 0,
    volume_24h      NUMERIC(20,4) DEFAULT 0,
    change_24h_pct  NUMERIC(10,4) DEFAULT 0,
    vwap            NUMERIC(20,8) DEFAULT 0,
    high_24h        NUMERIC(20,8) DEFAULT 0,
    low_24h         NUMERIC(20,8) DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_focus_updated ON market_snapshot_focus(updated_at);


-- ═══════════════════════════════════════════════════════════════
-- 3. market_snapshot_scout — broad universe (30s flush)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS market_snapshot_scout (
    symbol          TEXT PRIMARY KEY,
    bid             NUMERIC(20,8) NOT NULL DEFAULT 0,
    ask             NUMERIC(20,8) NOT NULL DEFAULT 0,
    mid             NUMERIC(20,8) NOT NULL DEFAULT 0,
    volume_24h      NUMERIC(20,4) DEFAULT 0,
    change_24h_pct  NUMERIC(10,4) DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scout_updated ON market_snapshot_scout(updated_at);


-- ═══════════════════════════════════════════════════════════════
-- 4. market_sparkline_points — mini price charts (15-min buckets)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS market_sparkline_points (
    symbol          TEXT NOT NULL,
    ts              TIMESTAMPTZ NOT NULL,
    price           NUMERIC(20,8) NOT NULL,
    PRIMARY KEY (symbol, ts)
);

-- Partition-friendly index for recent lookups
CREATE INDEX IF NOT EXISTS idx_sparkline_symbol_ts ON market_sparkline_points(symbol, ts DESC);


-- ═══════════════════════════════════════════════════════════════
-- 5. mover_events — momentum/volume breakout alerts
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS mover_events (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    symbol          TEXT NOT NULL,
    event_type      TEXT NOT NULL,               -- "momentum_1h" | "volume_accel" | "spread_widen"
    magnitude       NUMERIC(10,4) NOT NULL,      -- e.g. 5.2 for 5.2% move
    direction       TEXT DEFAULT 'up',            -- "up" | "down"
    metadata        JSONB DEFAULT '{}',
    detected_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mover_detected ON mover_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_mover_symbol ON mover_events(symbol, detected_at DESC);


-- ═══════════════════════════════════════════════════════════════
-- 6. market_focus_config — which pairs are in focus universe
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS market_focus_config (
    symbol          TEXT PRIMARY KEY,
    reason          TEXT NOT NULL DEFAULT 'manual',  -- "manual" | "favorite" | "position" | "mover"
    promoted_at     TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,                      -- NULL = permanent (favorites), set for movers
    metadata        JSONB DEFAULT '{}'
);


-- ═══════════════════════════════════════════════════════════════
-- Enable Realtime on focus table (for dashboard live updates)
-- ═══════════════════════════════════════════════════════════════
-- Note: Run this in the Supabase Dashboard SQL editor:
-- ALTER PUBLICATION supabase_realtime ADD TABLE market_snapshot_focus;
-- ALTER PUBLICATION supabase_realtime ADD TABLE mover_events;


-- ═══════════════════════════════════════════════════════════════
-- RLS policies (allow read for all, write from service role)
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE market_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_snapshot_focus ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_snapshot_scout ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_sparkline_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE mover_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_focus_config ENABLE ROW LEVEL SECURITY;

-- Public read
CREATE POLICY "market_catalog_read" ON market_catalog FOR SELECT USING (true);
CREATE POLICY "market_focus_read" ON market_snapshot_focus FOR SELECT USING (true);
CREATE POLICY "market_scout_read" ON market_snapshot_scout FOR SELECT USING (true);
CREATE POLICY "sparkline_read" ON market_sparkline_points FOR SELECT USING (true);
CREATE POLICY "movers_read" ON mover_events FOR SELECT USING (true);
CREATE POLICY "focus_config_read" ON market_focus_config FOR SELECT USING (true);

-- Service role write (all operations)
CREATE POLICY "market_catalog_write" ON market_catalog FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "market_focus_write" ON market_snapshot_focus FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "market_scout_write" ON market_snapshot_scout FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "sparkline_write" ON market_sparkline_points FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "movers_write" ON mover_events FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "focus_config_write" ON market_focus_config FOR ALL USING (auth.role() = 'service_role');
