-- Migration 001: V4 Base Tables
-- Timestamp: 2026-02-10
-- Description: Core tables for paper trading system
-- This is the canonical migration. The schema_v4*.sql files at root are kept for reference.

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Users & Accounts ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discord_id TEXT UNIQUE NOT NULL,
    username TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_seen TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id),
    instance_id TEXT DEFAULT 'default',
    equity NUMERIC(12, 2) DEFAULT 2000.00,
    cash NUMERIC(12, 2) DEFAULT 2000.00,
    buying_power NUMERIC(12, 2) DEFAULT 2000.00,
    pdt_count INT DEFAULT 0,
    day_trades_history JSONB DEFAULT '[]'::JSONB,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Performance Tracking ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.daily_pnl (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES public.accounts(id),
    date DATE DEFAULT CURRENT_DATE,
    start_equity NUMERIC(12, 2),
    end_equity NUMERIC(12, 2),
    realized_pnl NUMERIC(12, 2) DEFAULT 0,
    unrealized_pnl NUMERIC(12, 2) DEFAULT 0,
    trades_count INT DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS daily_pnl_account_date_idx ON public.daily_pnl(account_id, date);

-- ─── Trades ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES public.accounts(id),
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    strategy_version TEXT DEFAULT '1.0.0',
    status TEXT DEFAULT 'open',
    entry_time TIMESTAMPTZ DEFAULT now(),
    exit_time TIMESTAMPTZ,
    entry_price NUMERIC(12, 4),
    exit_price NUMERIC(12, 4),
    quantity INT DEFAULT 1,
    pnl NUMERIC(12, 2),
    legs JSONB DEFAULT '[]'::JSONB,
    greeks_at_entry JSONB,
    risk_at_entry JSONB,
    score_at_entry JSONB,
    notes TEXT
);

-- ─── Orders ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID REFERENCES public.trades(id),
    account_id UUID REFERENCES public.accounts(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    type TEXT DEFAULT 'limit',
    price NUMERIC(12, 4),
    quantity INT NOT NULL,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMPTZ DEFAULT now(),
    filled_at TIMESTAMPTZ,
    filled_price NUMERIC(12, 4),
    slippage_bps NUMERIC(8, 2) DEFAULT 0,
    legs JSONB NOT NULL DEFAULT '[]'::JSONB,
    meta JSONB
);

-- ─── Fills ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.fills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES public.orders(id),
    trade_id UUID REFERENCES public.trades(id),
    timestamp TIMESTAMPTZ DEFAULT now(),
    symbol TEXT,
    side TEXT,
    quantity INT,
    price NUMERIC(12, 4),
    slippage NUMERIC(12, 4) DEFAULT 0,
    fee NUMERIC(12, 2) DEFAULT 0
);

-- ─── Positions ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES public.accounts(id),
    symbol TEXT NOT NULL,
    underlying TEXT,
    quantity INT DEFAULT 0,
    avg_price NUMERIC(12, 4),
    current_price NUMERIC(12, 4),
    market_value NUMERIC(12, 4),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS positions_account_symbol_idx ON public.positions(account_id, symbol);

-- ─── PnL Timeseries ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.pnl_timeseries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES public.accounts(id),
    timestamp TIMESTAMPTZ DEFAULT now(),
    equity NUMERIC(12, 2),
    cash NUMERIC(12, 2),
    unrealized_pnl NUMERIC(12, 2),
    realized_pnl NUMERIC(12, 2),
    drawdown NUMERIC(8, 4) DEFAULT 0
);
CREATE INDEX IF NOT EXISTS pnl_ts_account_time_idx ON public.pnl_timeseries(account_id, timestamp);

-- ─── Option Chain Snapshots ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.option_chain_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    underlying TEXT NOT NULL,
    snapshot_time TIMESTAMPTZ DEFAULT now(),
    contracts JSONB NOT NULL DEFAULT '[]'::JSONB,
    contract_count INT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ocs_underlying_time_idx ON public.option_chain_snapshots(underlying, snapshot_time);

-- ─── Research ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.research_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL,
    symbol TEXT,
    title TEXT,
    content TEXT,
    sentiment_score NUMERIC(5, 3),
    relevance_score NUMERIC(5, 3),
    fetched_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB
);
CREATE INDEX IF NOT EXISTS ri_symbol_time_idx ON public.research_items(symbol, fetched_at);

-- ─── Features Daily ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.features_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    features JSONB NOT NULL DEFAULT '{}'::JSONB,
    source_ids TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS fd_symbol_date_idx ON public.features_daily(symbol, date);

-- ─── Strategy Registry ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.strategy_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    version TEXT DEFAULT '1.0.0',
    status TEXT DEFAULT 'candidate',
    description TEXT,
    parameters JSONB DEFAULT '{}'::JSONB,
    gate_criteria JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Experiment Runs ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.experiment_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID REFERENCES public.strategy_registry(id),
    strategy_version TEXT,
    start_date DATE,
    end_date DATE,
    status TEXT DEFAULT 'running',
    metrics JSONB,
    passed_gates BOOLEAN DEFAULT false,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Health Reports ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.health_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ DEFAULT now(),
    overall_status TEXT NOT NULL,
    components JSONB DEFAULT '[]'::JSONB,
    tests_passed INT DEFAULT 0,
    tests_failed INT DEFAULT 0,
    lint_errors INT DEFAULT 0,
    typecheck_errors INT DEFAULT 0,
    simulation_result TEXT,
    notes TEXT
);

-- ─── Daily Gameplans ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.daily_gameplans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    instance_id TEXT DEFAULT 'default',
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(date, instance_id)
);

CREATE TABLE IF NOT EXISTS public.daily_gameplan_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id UUID REFERENCES public.daily_gameplans(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    catalyst_summary TEXT,
    regime TEXT,
    ivr_tech_snapshot TEXT,
    preferred_strategy TEXT,
    risk_tier TEXT,
    do_not_trade BOOLEAN DEFAULT false,
    visual_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Audit & Config ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor TEXT DEFAULT 'zoe',
    action TEXT NOT NULL,
    details JSONB,
    severity TEXT DEFAULT 'info',
    timestamp TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.health_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    timestamp TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── RLS Policies ─────────────────────────────────────────────────────
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "allow_public_read_daily_pnl" ON public.daily_pnl;
DROP POLICY IF EXISTS "allow_public_read_trades" ON public.trades;
DROP POLICY IF EXISTS "allow_public_read_positions" ON public.positions;

CREATE POLICY "allow_public_read_daily_pnl" ON public.daily_pnl FOR SELECT USING (true);
CREATE POLICY "allow_public_read_trades" ON public.trades FOR SELECT USING (true);
CREATE POLICY "allow_public_read_positions" ON public.positions FOR SELECT USING (true);

ALTER TABLE public.daily_gameplans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_gameplan_items ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_public_read_gameplans" ON public.daily_gameplans;
DROP POLICY IF EXISTS "allow_public_read_gameplan_items" ON public.daily_gameplan_items;
CREATE POLICY "allow_public_read_gameplans" ON public.daily_gameplans FOR SELECT USING (true);
CREATE POLICY "allow_public_read_gameplan_items" ON public.daily_gameplan_items FOR SELECT USING (true);
