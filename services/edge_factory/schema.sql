-- ============================================================
-- EDGE FACTORY SCHEMA (Supabase / PostgreSQL)
-- Run in Supabase SQL Editor. Idempotent.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Feature Store ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    value NUMERIC(20, 8) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS idx_ef_features_symbol_name
    ON public.ef_features(symbol, feature_name, computed_at DESC);

-- ── Regime States ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_regimes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    regime TEXT NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    features_used JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS idx_ef_regimes_detected
    ON public.ef_regimes(detected_at DESC);

-- ── Signals ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    strength NUMERIC(5, 4) NOT NULL,
    regime_id UUID REFERENCES public.ef_regimes(id),
    features JSONB NOT NULL DEFAULT '{}'::JSONB,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    strategy_name TEXT NOT NULL,
    acted_on BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_ef_signals_symbol_time
    ON public.ef_signals(symbol, generated_at DESC);

-- ── Positions ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'buy',
    entry_price NUMERIC(20, 8),
    entry_time TIMESTAMPTZ,
    size_usd NUMERIC(10, 2),
    tp_price NUMERIC(20, 8),
    sl_price NUMERIC(20, 8),
    status TEXT NOT NULL DEFAULT 'pending',
    exit_price NUMERIC(20, 8),
    exit_time TIMESTAMPTZ,
    pnl_usd NUMERIC(10, 4),
    signal_id UUID REFERENCES public.ef_signals(id),
    order_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ef_positions_status
    ON public.ef_positions(status);

CREATE INDEX IF NOT EXISTS idx_ef_positions_symbol
    ON public.ef_positions(symbol, created_at DESC);

-- ── Key-Value State (kill switch, circuit breaker, HWM) ──────
CREATE TABLE IF NOT EXISTS public.ef_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── V2: Slippage Columns on Positions ─────────────────────────
ALTER TABLE public.ef_positions ADD COLUMN IF NOT EXISTS reference_mid NUMERIC(20, 8);
ALTER TABLE public.ef_positions ADD COLUMN IF NOT EXISTS slippage_vs_mid_bps NUMERIC(10, 4);
ALTER TABLE public.ef_positions ADD COLUMN IF NOT EXISTS execution_mode TEXT;

-- ── V2: Slippage Log ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_slippage_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    reference_mid NUMERIC(20, 8),
    fill_price NUMERIC(20, 8),
    slippage_bps NUMERIC(10, 4),
    spread_bps NUMERIC(10, 4),
    execution_mode TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ef_slippage_log_symbol
    ON public.ef_slippage_log(symbol, created_at DESC);

ALTER TABLE public.ef_slippage_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_ef_slippage_log" ON public.ef_slippage_log;
CREATE POLICY "allow_all_ef_slippage_log" ON public.ef_slippage_log FOR ALL USING (true);

-- ── V2: Intraday Regime Log ──────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_intraday_regime_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    regime TEXT NOT NULL,
    reason TEXT,
    features JSONB NOT NULL DEFAULT '{}'::JSONB,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ef_intraday_regime_log_time
    ON public.ef_intraday_regime_log(detected_at DESC);

ALTER TABLE public.ef_intraday_regime_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_ef_intraday_regime_log" ON public.ef_intraday_regime_log;
CREATE POLICY "allow_all_ef_intraday_regime_log" ON public.ef_intraday_regime_log FOR ALL USING (true);

-- ── V2: Signal mode column ──────────────────────────────────
ALTER TABLE public.ef_signals ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'swing';

-- ── Row Level Security ───────────────────────────────────────
ALTER TABLE public.ef_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_regimes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_state ENABLE ROW LEVEL SECURITY;

-- Drop-and-recreate for idempotency
DROP POLICY IF EXISTS "allow_all_ef_features" ON public.ef_features;
DROP POLICY IF EXISTS "allow_all_ef_regimes" ON public.ef_regimes;
DROP POLICY IF EXISTS "allow_all_ef_signals" ON public.ef_signals;
DROP POLICY IF EXISTS "allow_all_ef_positions" ON public.ef_positions;
DROP POLICY IF EXISTS "allow_all_ef_state" ON public.ef_state;

-- Service role has full access; dashboard has read access
CREATE POLICY "allow_all_ef_features" ON public.ef_features FOR ALL USING (true);
CREATE POLICY "allow_all_ef_regimes" ON public.ef_regimes FOR ALL USING (true);
CREATE POLICY "allow_all_ef_signals" ON public.ef_signals FOR ALL USING (true);
CREATE POLICY "allow_all_ef_positions" ON public.ef_positions FOR ALL USING (true);
CREATE POLICY "allow_all_ef_state" ON public.ef_state FOR ALL USING (true);
