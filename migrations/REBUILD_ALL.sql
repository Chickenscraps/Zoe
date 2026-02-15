-- ============================================================================
-- REBUILD_ALL.sql — Consolidated schema for OpenClaw / ZOE Terminal
-- Generated: 2026-02-14
-- Target: Empty Supabase Postgres database (all tables freshly dropped)
--
-- Sources consolidated (in order):
--   1. infra/db/migrations/001_v4_base_tables.sql
--   2. migrations/20260211_full_setup.sql
--   3. migrations/20260211_trendlines_and_bounce.sql
--   4. migrations/20260212_add_mode_and_boot_tables.sql
--   5. migrations/20260211_crypto_live_trading.sql
--   6. migrations/20260212_crypto_candles.sql
--   7. migrations/20260213_market_data_tables.sql
--   8. migrations/20260213_accounting_tables.sql
--   9. migrations/20260213_order_lifecycle_tables.sql
--  10. supabase_audit/migrations/003_create_health_and_reconcile.sql
--  11. supabase_audit/migrations/006_config_versioning.sql
--  12. supabase_audit/migrations/002_add_idempotency_and_trace.sql
--  13. zoe-terminal/src/lib/types.ts (column reference for tables without SQL DDL)
-- ============================================================================

BEGIN;

-- ═══════════════════════════════════════════════════════════════
-- 0. EXTENSIONS
-- ═══════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════
-- 1. V4 BASE TABLES (paper trading core)
-- ═══════════════════════════════════════════════════════════════

-- ─── Users & Accounts ─────────────────────────────────────────
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
    equity NUMERIC(12,2) DEFAULT 2000.00,
    cash NUMERIC(12,2) DEFAULT 2000.00,
    buying_power NUMERIC(12,2) DEFAULT 2000.00,
    pdt_count INT DEFAULT 0,
    day_trades_history JSONB DEFAULT '[]'::JSONB,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Performance Tracking ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.daily_pnl (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES public.accounts(id),
    date DATE DEFAULT CURRENT_DATE,
    start_equity NUMERIC(12,2),
    end_equity NUMERIC(12,2),
    realized_pnl NUMERIC(12,2) DEFAULT 0,
    unrealized_pnl NUMERIC(12,2) DEFAULT 0,
    trades_count INT DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS daily_pnl_account_date_idx ON public.daily_pnl(account_id, date);

-- ─── Trades ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES public.accounts(id),
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    strategy_version TEXT DEFAULT '1.0.0',
    status TEXT DEFAULT 'open',
    entry_time TIMESTAMPTZ DEFAULT now(),
    exit_time TIMESTAMPTZ,
    entry_price NUMERIC(12,4),
    exit_price NUMERIC(12,4),
    quantity INT DEFAULT 1,
    pnl NUMERIC(12,2),
    legs JSONB DEFAULT '[]'::JSONB,
    greeks_at_entry JSONB,
    risk_at_entry JSONB,
    score_at_entry JSONB,
    notes TEXT
);

-- ─── Orders (paper) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID REFERENCES public.trades(id),
    account_id UUID REFERENCES public.accounts(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    type TEXT DEFAULT 'limit',
    price NUMERIC(12,4),
    quantity INT NOT NULL,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMPTZ DEFAULT now(),
    filled_at TIMESTAMPTZ,
    filled_price NUMERIC(12,4),
    slippage_bps NUMERIC(8,2) DEFAULT 0,
    legs JSONB NOT NULL DEFAULT '[]'::JSONB,
    meta JSONB
);

-- ─── Fills (paper) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.fills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES public.orders(id),
    trade_id UUID REFERENCES public.trades(id),
    timestamp TIMESTAMPTZ DEFAULT now(),
    symbol TEXT,
    side TEXT,
    quantity INT,
    price NUMERIC(12,4),
    slippage NUMERIC(12,4) DEFAULT 0,
    fee NUMERIC(12,2) DEFAULT 0
);

-- ─── Positions (paper) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES public.accounts(id),
    symbol TEXT NOT NULL,
    underlying TEXT,
    quantity INT DEFAULT 0,
    avg_price NUMERIC(12,4),
    current_price NUMERIC(12,4),
    market_value NUMERIC(12,4),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS positions_account_symbol_idx ON public.positions(account_id, symbol);

-- ─── PnL Timeseries ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.pnl_timeseries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES public.accounts(id),
    timestamp TIMESTAMPTZ DEFAULT now(),
    equity NUMERIC(12,2),
    cash NUMERIC(12,2),
    unrealized_pnl NUMERIC(12,2),
    realized_pnl NUMERIC(12,2),
    drawdown NUMERIC(8,4) DEFAULT 0
);
CREATE INDEX IF NOT EXISTS pnl_ts_account_time_idx ON public.pnl_timeseries(account_id, timestamp);

-- ─── Option Chain Snapshots ──────────────────────────────────
CREATE TABLE IF NOT EXISTS public.option_chain_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    underlying TEXT NOT NULL,
    snapshot_time TIMESTAMPTZ DEFAULT now(),
    contracts JSONB NOT NULL DEFAULT '[]'::JSONB,
    contract_count INT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ocs_underlying_time_idx ON public.option_chain_snapshots(underlying, snapshot_time);

-- ─── Research ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.research_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL,
    symbol TEXT,
    title TEXT,
    content TEXT,
    sentiment_score NUMERIC(5,3),
    relevance_score NUMERIC(5,3),
    fetched_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB
);
CREATE INDEX IF NOT EXISTS ri_symbol_time_idx ON public.research_items(symbol, fetched_at);

-- ─── Features Daily ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.features_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    features JSONB NOT NULL DEFAULT '{}'::JSONB,
    source_ids TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS fd_symbol_date_idx ON public.features_daily(symbol, date);

-- ─── Strategy Registry ───────────────────────────────────────
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

-- ─── Experiment Runs ─────────────────────────────────────────
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

-- ─── Health Reports ──────────────────────────────────────────
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

-- ─── Health Events ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.health_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    timestamp TIMESTAMPTZ DEFAULT now()
);

-- ─── Audit Log (v4 base) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor TEXT DEFAULT 'zoe',
    action TEXT NOT NULL,
    details JSONB,
    severity TEXT DEFAULT 'info',
    timestamp TIMESTAMPTZ DEFAULT now()
);

-- ─── Config ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);


-- ═══════════════════════════════════════════════════════════════
-- 2. CRYPTO CORE TABLES (Kraken live trading)
--    Merges: full_setup, crypto_live_trading, crypto_prod, mode migration
-- ═══════════════════════════════════════════════════════════════

-- ─── Crypto Orders ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_order_id TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type TEXT NOT NULL CHECK (order_type IN ('market', 'limit')),
    qty NUMERIC,
    notional NUMERIC,
    limit_price NUMERIC,
    status TEXT NOT NULL CHECK (status IN ('new', 'submitted', 'partially_filled', 'filled', 'canceled', 'rejected', 'cancel_pending', 'working')),
    filled_qty NUMERIC DEFAULT 0,
    filled_avg_price NUMERIC DEFAULT 0,
    fees NUMERIC DEFAULT 0,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_response JSONB NOT NULL DEFAULT '{}'::JSONB,
    replace_count INT DEFAULT 0,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    -- idempotency & tracing (from 002_add_idempotency_and_trace)
    idempotency_key TEXT,
    broker_order_id TEXT,
    trace_id TEXT
);

CREATE INDEX IF NOT EXISTS crypto_orders_status_requested_at_idx
    ON public.crypto_orders(status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_crypto_orders_mode ON public.crypto_orders(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_orders_mode_status
    ON public.crypto_orders(mode, status, requested_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_crypto_orders_idempotency
    ON public.crypto_orders(mode, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_crypto_orders_broker_id
    ON public.crypto_orders(mode, broker_order_id)
    WHERE broker_order_id IS NOT NULL;

-- ─── Crypto Fills ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_fills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES public.crypto_orders(id) ON DELETE CASCADE,
    fill_id TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    qty NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    fee NUMERIC NOT NULL DEFAULT 0,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_fill JSONB NOT NULL DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    -- accounting fields (from 20260213_accounting_tables)
    broker_fee NUMERIC(20,8) DEFAULT 0,
    fee_currency TEXT DEFAULT 'USD',
    broker_fill_id TEXT,
    exchange TEXT DEFAULT 'kraken',
    -- tracing (from 002_add_idempotency_and_trace)
    trace_id TEXT
);

CREATE INDEX IF NOT EXISTS crypto_fills_order_id_executed_at_idx
    ON public.crypto_fills(order_id, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_crypto_fills_mode ON public.crypto_fills(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_fills_mode_executed
    ON public.crypto_fills(mode, executed_at DESC);

-- ─── Crypto Positions ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_positions (
    symbol TEXT PRIMARY KEY,
    qty NUMERIC NOT NULL DEFAULT 0,
    avg_cost NUMERIC NOT NULL DEFAULT 0,
    current_price NUMERIC,
    market_value NUMERIC,
    unrealized_pnl NUMERIC,
    unrealized_pnl_pct NUMERIC,
    last_updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Crypto Holdings Snapshots ───────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_holdings_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taken_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    holdings JSONB NOT NULL,
    total_crypto_value NUMERIC NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'kraken',
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS crypto_holdings_snapshots_taken_at_idx
    ON public.crypto_holdings_snapshots(taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_crypto_holdings_snapshots_mode
    ON public.crypto_holdings_snapshots(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_holdings_mode_taken
    ON public.crypto_holdings_snapshots(mode, taken_at DESC);

-- ─── Crypto Cash Snapshots ───────────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_cash_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taken_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cash_available NUMERIC NOT NULL DEFAULT 0,
    buying_power NUMERIC NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'kraken',
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS crypto_cash_snapshots_taken_at_idx
    ON public.crypto_cash_snapshots(taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_crypto_cash_snapshots_mode
    ON public.crypto_cash_snapshots(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_cash_mode_taken
    ON public.crypto_cash_snapshots(mode, taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_crypto_cash_mode_taken_asc
    ON public.crypto_cash_snapshots(mode, taken_at ASC);

-- ─── Crypto Candles (OHLCV) ─────────────────────────────────
--    Uses identity PK + open_time as double precision (unix ts)
CREATE TABLE IF NOT EXISTS public.crypto_candles (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time DOUBLE PRECISION NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION DEFAULT 0,
    patterns JSONB DEFAULT NULL,
    mode TEXT NOT NULL DEFAULT 'paper',
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT crypto_candles_unique UNIQUE (symbol, timeframe, open_time, mode)
);

CREATE INDEX IF NOT EXISTS idx_crypto_candles_lookup
    ON public.crypto_candles(symbol, timeframe, mode, open_time DESC);

-- ─── Crypto Tickers ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_tickers (
    symbol TEXT PRIMARY KEY,
    price NUMERIC NOT NULL,
    change_24h NUMERIC,
    last_updated TIMESTAMPTZ DEFAULT now()
);

-- ─── Crypto Indicators ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_indicators (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bucket TIMESTAMPTZ NOT NULL,
    sma_50 NUMERIC,
    sma_200 NUMERIC,
    rsi_14 NUMERIC,
    regime TEXT,
    signal TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (symbol, timeframe, bucket)
);

-- ─── Crypto Audit Log ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ DEFAULT now(),
    component TEXT NOT NULL,
    event TEXT NOT NULL,
    level TEXT DEFAULT 'info',
    details JSONB
);

-- ─── Crypto Reconciliation Events ────────────────────────────
CREATE TABLE IF NOT EXISTS public.crypto_reconciliation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taken_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    local_cash NUMERIC,
    rh_cash NUMERIC,
    cash_diff NUMERIC,
    local_holdings JSONB,
    rh_holdings JSONB,
    holdings_diff JSONB,
    status TEXT NOT NULL CHECK (status IN ('ok', 'degraded', 'error')),
    reason TEXT,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS crypto_reconciliation_events_taken_at_idx
    ON public.crypto_reconciliation_events(taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_crypto_reconciliation_events_mode
    ON public.crypto_reconciliation_events(mode);
CREATE INDEX IF NOT EXISTS idx_crypto_reconcile_mode_taken
    ON public.crypto_reconciliation_events(mode, taken_at DESC);

-- ─── Daily Notional ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.daily_notional (
    day DATE NOT NULL DEFAULT current_date,
    amount NUMERIC DEFAULT 0,
    notional_used NUMERIC NOT NULL DEFAULT 0,
    notional_limit NUMERIC DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT now(),
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    PRIMARY KEY (day, mode)
);

-- ─── Daily Gameplans ─────────────────────────────────────────
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


-- ═══════════════════════════════════════════════════════════════
-- 3. TRENDLINES + KEY LEVELS + BOUNCE CATCHER
-- ═══════════════════════════════════════════════════════════════

-- ─── Market Pivots ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.market_pivots (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price NUMERIC NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('high', 'low')),
    source TEXT NOT NULL CHECK (source IN ('wick', 'body')),
    atr_snapshot NUMERIC,
    confirmed BOOLEAN NOT NULL DEFAULT true,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, timeframe, timestamp, type, source)
);

CREATE INDEX IF NOT EXISTS idx_pivots_lookup
    ON public.market_pivots(symbol, timeframe, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_pivots_type_source
    ON public.market_pivots(symbol, timeframe, type, source);

-- ─── Technical Trendlines ────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.technical_trendlines (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('support', 'resistance')),
    slope NUMERIC NOT NULL,
    intercept NUMERIC NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    inlier_count INT NOT NULL,
    score NUMERIC NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    is_active BOOLEAN NOT NULL DEFAULT true,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trendlines_lookup
    ON public.technical_trendlines(symbol, timeframe, is_active, updated_at DESC);

-- ─── Technical Levels ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.technical_levels (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    price_centroid NUMERIC NOT NULL,
    price_top NUMERIC NOT NULL,
    price_bottom NUMERIC NOT NULL,
    role TEXT CHECK (role IN ('support', 'resistance', 'flip')),
    touch_count INT NOT NULL DEFAULT 0,
    score NUMERIC NOT NULL DEFAULT 0,
    first_tested TIMESTAMPTZ,
    last_tested TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_levels_lookup
    ON public.technical_levels(symbol, timeframe, is_active, score DESC);
CREATE INDEX IF NOT EXISTS idx_levels_price_range
    ON public.technical_levels(symbol, timeframe, price_bottom, price_top);

-- ─── Structure Events ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.structure_events (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('breakout', 'breakdown', 'retest')),
    reference_id BIGINT,
    reference_kind TEXT CHECK (reference_kind IN ('trendline', 'level')),
    price_at NUMERIC NOT NULL,
    confirmed BOOLEAN NOT NULL DEFAULT false,
    confirm_count INT NOT NULL DEFAULT 0,
    reason_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_structure_events_lookup
    ON public.structure_events(symbol, timeframe, ts DESC);

-- ─── Bounce Events ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.bounce_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol TEXT NOT NULL,
    prev_state TEXT,
    state TEXT NOT NULL,
    score INTEGER,
    reason_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_bounce_events_symbol_ts
    ON public.bounce_events(symbol, ts DESC);

-- ─── Bounce Intents ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.bounce_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol TEXT NOT NULL,
    entry_style TEXT CHECK (entry_style IN ('retest', 'breakout')),
    entry_price NUMERIC,
    expected_move_pct NUMERIC,
    tp_price NUMERIC,
    sl_price NUMERIC,
    score INTEGER,
    components_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    blocked BOOLEAN NOT NULL DEFAULT false,
    blocked_reason TEXT,
    executed BOOLEAN NOT NULL DEFAULT false,
    reason_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_bounce_intents_symbol_ts
    ON public.bounce_intents(symbol, ts DESC);


-- ═══════════════════════════════════════════════════════════════
-- 4. PNL DAILY + CANDIDATE SCANS + THOUGHTS + HEALTH HEARTBEAT
--    (Tables whose CREATE TABLE was never in SQL files;
--     schemas inferred from types.ts + Python upsert code)
-- ═══════════════════════════════════════════════════════════════

-- ─── PnL Daily ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.pnl_daily (
    date DATE NOT NULL,
    instance_id TEXT NOT NULL DEFAULT 'default',
    daily_pnl NUMERIC DEFAULT 0,
    equity NUMERIC DEFAULT 0,
    drawdown NUMERIC DEFAULT 0,
    win_rate NUMERIC,
    expectancy NUMERIC,
    cash_buffer_pct NUMERIC DEFAULT 0,
    day_trades_used INT DEFAULT 0,
    realized_pnl NUMERIC DEFAULT 0,
    unrealized_pnl NUMERIC DEFAULT 0,
    -- accounting extension columns
    fees_paid NUMERIC(20,8) DEFAULT 0,
    gross_equity NUMERIC(20,8),
    net_equity NUMERIC(20,8),
    net_deposits NUMERIC(20,8) DEFAULT 0,
    crypto_value NUMERIC(20,8) DEFAULT 0,
    cash_usd NUMERIC(20,8) DEFAULT 0,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    PRIMARY KEY (date, instance_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_pnl_daily_mode ON public.pnl_daily(mode);
CREATE INDEX IF NOT EXISTS idx_pnl_daily_mode_date ON public.pnl_daily(mode, date ASC);

-- ─── Candidate Scans ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.candidate_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id TEXT NOT NULL DEFAULT 'default',
    symbol TEXT NOT NULL,
    score NUMERIC NOT NULL DEFAULT 0,
    score_breakdown JSONB DEFAULT '{}'::JSONB,
    info JSONB DEFAULT '{}'::JSONB,
    recommended_strategy TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_candidate_scans_mode ON public.candidate_scans(mode);
CREATE INDEX IF NOT EXISTS idx_candidate_scans_mode_created
    ON public.candidate_scans(mode, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_scans_mode_symbol_created
    ON public.candidate_scans(mode, symbol, created_at DESC);

-- ─── Thoughts ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.thoughts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id TEXT NOT NULL DEFAULT 'default',
    content TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('scan', 'entry', 'exit', 'health', 'general')),
    symbol TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_thoughts_mode ON public.thoughts(mode);
CREATE INDEX IF NOT EXISTS idx_thoughts_mode_created
    ON public.thoughts(mode, created_at DESC);

-- ─── Health Heartbeat ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.health_heartbeat (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id TEXT NOT NULL DEFAULT 'default',
    component TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'warning', 'error', 'down', 'degraded')),
    last_heartbeat TIMESTAMPTZ DEFAULT now(),
    message TEXT,
    details JSONB DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE UNIQUE INDEX IF NOT EXISTS health_heartbeat_instance_component_mode_idx
    ON public.health_heartbeat(instance_id, component, mode);
CREATE INDEX IF NOT EXISTS idx_health_heartbeat_mode
    ON public.health_heartbeat(mode, instance_id, component);

-- ─── Risk Events ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id TEXT NOT NULL DEFAULT 'default',
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Copilot Messages ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.copilot_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    context_page TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);


-- ═══════════════════════════════════════════════════════════════
-- 5. BOOT RECONCILIATION (agent_state + boot_audit)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.agent_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    instance_id TEXT NOT NULL DEFAULT 'default',
    state JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (mode, instance_id)
);

CREATE TABLE IF NOT EXISTS public.boot_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    instance_id TEXT NOT NULL DEFAULT 'default',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'ok', 'safe_mode', 'halted', 'error')),
    diffs JSONB DEFAULT '{}',
    integrity_checks JSONB DEFAULT '{}',
    resume_policy TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ═══════════════════════════════════════════════════════════════
-- 6. MARKET DATA TABLES (market scanner)
-- ═══════════════════════════════════════════════════════════════

-- ─── Market Catalog ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.market_catalog (
    symbol TEXT PRIMARY KEY,
    exchange_symbol TEXT NOT NULL,
    ws_symbol TEXT,
    base TEXT NOT NULL,
    quote TEXT NOT NULL DEFAULT 'USD',
    exchange TEXT NOT NULL DEFAULT 'kraken',
    status TEXT NOT NULL DEFAULT 'active',
    min_qty NUMERIC(20,10) DEFAULT 0,
    lot_size NUMERIC(20,10) DEFAULT 0,
    tick_size NUMERIC(20,10) DEFAULT 0,
    fee_maker_pct NUMERIC(8,4) DEFAULT 0.16,
    fee_taker_pct NUMERIC(8,4) DEFAULT 0.26,
    ordermin NUMERIC(20,10) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    discovered_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_market_catalog_base ON public.market_catalog(base);
CREATE INDEX IF NOT EXISTS idx_market_catalog_status ON public.market_catalog(status);
CREATE INDEX IF NOT EXISTS idx_market_catalog_updated ON public.market_catalog(updated_at);

-- ─── Market Snapshot Focus ───────────────────────────────────
CREATE TABLE IF NOT EXISTS public.market_snapshot_focus (
    symbol TEXT PRIMARY KEY,
    bid NUMERIC(20,8) NOT NULL DEFAULT 0,
    ask NUMERIC(20,8) NOT NULL DEFAULT 0,
    mid NUMERIC(20,8) NOT NULL DEFAULT 0,
    spread_pct NUMERIC(10,6) DEFAULT 0,
    volume_24h NUMERIC(20,4) DEFAULT 0,
    change_24h_pct NUMERIC(10,4) DEFAULT 0,
    vwap NUMERIC(20,8) DEFAULT 0,
    high_24h NUMERIC(20,8) DEFAULT 0,
    low_24h NUMERIC(20,8) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_focus_updated ON public.market_snapshot_focus(updated_at);

-- ─── Market Snapshot Scout ───────────────────────────────────
CREATE TABLE IF NOT EXISTS public.market_snapshot_scout (
    symbol TEXT PRIMARY KEY,
    bid NUMERIC(20,8) NOT NULL DEFAULT 0,
    ask NUMERIC(20,8) NOT NULL DEFAULT 0,
    mid NUMERIC(20,8) NOT NULL DEFAULT 0,
    spread_pct NUMERIC(10,6) DEFAULT 0,
    volume_24h NUMERIC(20,4) DEFAULT 0,
    change_24h_pct NUMERIC(10,4) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scout_updated ON public.market_snapshot_scout(updated_at);

-- ─── Market Sparkline Points ─────────────────────────────────
CREATE TABLE IF NOT EXISTS public.market_sparkline_points (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    price NUMERIC(20,8) NOT NULL,
    PRIMARY KEY (symbol, ts)
);

CREATE INDEX IF NOT EXISTS idx_sparkline_symbol_ts ON public.market_sparkline_points(symbol, ts DESC);

-- ─── Mover Events ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.mover_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    magnitude NUMERIC(10,4) NOT NULL,
    direction TEXT DEFAULT 'up',
    metadata JSONB DEFAULT '{}',
    detected_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mover_detected ON public.mover_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_mover_symbol ON public.mover_events(symbol, detected_at DESC);

-- ─── Market Focus Config ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.market_focus_config (
    symbol TEXT PRIMARY KEY,
    reason TEXT NOT NULL DEFAULT 'manual',
    promoted_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);


-- ═══════════════════════════════════════════════════════════════
-- 7. ACCOUNTING TABLES (cash_events + fee_ledger)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.cash_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type IN ('deposit', 'withdrawal', 'transfer_in', 'transfer_out')),
    amount NUMERIC(20,8) NOT NULL,
    currency TEXT DEFAULT 'USD',
    description TEXT DEFAULT '',
    external_ref TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    mode TEXT DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_cash_events_mode_created
    ON public.cash_events(mode, created_at DESC);

CREATE TABLE IF NOT EXISTS public.fee_ledger (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    fill_id TEXT NOT NULL,
    order_id TEXT DEFAULT '',
    symbol TEXT NOT NULL,
    fee_amount NUMERIC(20,8) NOT NULL DEFAULT 0,
    fee_currency TEXT DEFAULT 'USD',
    fee_type TEXT DEFAULT 'trading' CHECK (fee_type IN ('trading', 'withdrawal', 'deposit', 'other')),
    created_at TIMESTAMPTZ DEFAULT now(),
    mode TEXT DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    CONSTRAINT uq_fee_ledger_fill UNIQUE (fill_id)
);

CREATE INDEX IF NOT EXISTS idx_fee_ledger_mode_created
    ON public.fee_ledger(mode, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fee_ledger_symbol
    ON public.fee_ledger(symbol);


-- ═══════════════════════════════════════════════════════════════
-- 8. ORDER LIFECYCLE (intents, events, trade locks)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.order_intents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type TEXT DEFAULT 'limit' CHECK (order_type IN ('limit', 'market')),
    qty NUMERIC(20,8),
    notional NUMERIC(20,8),
    limit_price NUMERIC(20,8),
    engine TEXT DEFAULT '',
    mode TEXT DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    status TEXT DEFAULT 'created' CHECK (status IN (
        'created', 'submitted', 'acked', 'partial_fill',
        'cancel_requested', 'cancelled', 'replaced',
        'filled', 'rejected', 'expired', 'error'
    )),
    broker_order_id TEXT,
    fill_price NUMERIC(20,8),
    fill_qty NUMERIC(20,8),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_intents_status
    ON public.order_intents(status)
    WHERE status NOT IN ('filled', 'cancelled', 'replaced', 'rejected', 'expired');
CREATE INDEX IF NOT EXISTS idx_order_intents_symbol_mode
    ON public.order_intents(symbol, mode);
CREATE INDEX IF NOT EXISTS idx_order_intents_created
    ON public.order_intents(created_at DESC);

CREATE TABLE IF NOT EXISTS public.order_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES public.order_intents(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    broker_order_id TEXT,
    fill_price NUMERIC(20,8),
    fill_qty NUMERIC(20,8),
    fee NUMERIC(20,8),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_events_intent
    ON public.order_events(intent_id, created_at);

CREATE TABLE IF NOT EXISTS public.trade_locks (
    symbol TEXT NOT NULL,
    engine TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    locked_at TIMESTAMPTZ DEFAULT now(),
    lock_holder TEXT NOT NULL,
    PRIMARY KEY (symbol, engine, mode)
);


-- ═══════════════════════════════════════════════════════════════
-- 9. EDGE FACTORY (ef_*) TABLES
-- ═══════════════════════════════════════════════════════════════

-- ─── ef_features ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    value NUMERIC NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT now(),
    source TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_ef_features_mode_symbol_computed
    ON public.ef_features(mode, symbol, feature_name, computed_at DESC);

-- ─── ef_regimes ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_regimes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    regime TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    detected_at TIMESTAMPTZ DEFAULT now(),
    features_used JSONB DEFAULT '{}'::JSONB,
    mode TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_ef_regimes_mode_detected
    ON public.ef_regimes(mode, detected_at DESC);

-- ─── ef_signals ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    strength NUMERIC NOT NULL,
    regime_id UUID REFERENCES public.ef_regimes(id),
    features JSONB DEFAULT '{}'::JSONB,
    generated_at TIMESTAMPTZ DEFAULT now(),
    strategy_name TEXT NOT NULL,
    acted_on BOOLEAN DEFAULT false,
    mode TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_ef_signals_mode_symbol_generated
    ON public.ef_signals(mode, symbol, generated_at DESC);

-- ─── ef_positions ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price NUMERIC,
    entry_time TIMESTAMPTZ,
    size_usd NUMERIC,
    tp_price NUMERIC,
    sl_price NUMERIC,
    status TEXT NOT NULL,
    exit_price NUMERIC,
    exit_time TIMESTAMPTZ,
    pnl_usd NUMERIC,
    signal_id UUID REFERENCES public.ef_signals(id),
    order_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    mode TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('paper', 'live')),
    -- idempotency & tracing
    idempotency_key TEXT,
    trace_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_ef_positions_mode_status
    ON public.ef_positions(mode, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ef_positions_idempotency
    ON public.ef_positions(mode, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- ─── ef_state ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ef_state (
    key TEXT NOT NULL,
    value JSONB NOT NULL DEFAULT '{}'::JSONB,
    updated_at TIMESTAMPTZ DEFAULT now(),
    mode TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('paper', 'live')),
    CONSTRAINT ef_state_mode_key_unique UNIQUE (mode, key)
);


-- ═══════════════════════════════════════════════════════════════
-- 10. ZOE EVENTS + HEALTH + BROKER RECONCILIATION
--     (from supabase_audit/migrations/003)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.zoe_health (
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    last_quote_ts TIMESTAMPTZ,
    last_scan_ts TIMESTAMPTZ,
    last_trade_ts TIMESTAMPTZ,
    last_flush_ts TIMESTAMPTZ,
    last_reconcile_ts TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (status IN ('healthy', 'degraded', 'stale', 'offline', 'unknown')),
    warning_count INT NOT NULL DEFAULT 0,
    error_count INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (mode)
);

CREATE TABLE IF NOT EXISTS public.broker_reconciliation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    status TEXT NOT NULL CHECK (status IN ('ok', 'mismatch', 'error')),
    summary JSONB NOT NULL DEFAULT '{}',
    mismatches JSONB DEFAULT '{}',
    broker_positions JSONB DEFAULT '{}',
    local_positions JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_broker_reconciliation_mode_ts
    ON public.broker_reconciliation(mode, ts DESC);

CREATE TABLE IF NOT EXISTS public.zoe_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    seq BIGINT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    subtype TEXT NOT NULL,
    symbol TEXT,
    severity TEXT NOT NULL DEFAULT 'info'
        CHECK (severity IN ('info', 'good', 'bad', 'warn', 'neutral')),
    body TEXT NOT NULL,
    meta JSONB DEFAULT '{}',
    trace_id TEXT,
    config_version INT,
    idempotency_key TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE SEQUENCE IF NOT EXISTS zoe_events_seq_paper;
CREATE SEQUENCE IF NOT EXISTS zoe_events_seq_live;

CREATE INDEX IF NOT EXISTS idx_zoe_events_mode_ts
    ON public.zoe_events(mode, ts DESC);
CREATE INDEX IF NOT EXISTS idx_zoe_events_mode_seq
    ON public.zoe_events(mode, seq DESC);
CREATE INDEX IF NOT EXISTS idx_zoe_events_mode_symbol_ts
    ON public.zoe_events(mode, symbol, ts DESC);


-- ═══════════════════════════════════════════════════════════════
-- 11. CONFIG VERSIONING (strategy_configs + config_audit_log)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.strategy_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    version INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    config_json JSONB NOT NULL,
    checksum TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL DEFAULT 'system'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_configs_active
    ON public.strategy_configs(mode) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_strategy_configs_mode_version
    ON public.strategy_configs(mode, version DESC);

CREATE TABLE IF NOT EXISTS public.config_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    version INT NOT NULL,
    diff_json JSONB NOT NULL DEFAULT '{}',
    changed_by TEXT NOT NULL DEFAULT 'system',
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_config_audit_mode_version
    ON public.config_audit_log(mode, version DESC);

COMMIT;


-- ═══════════════════════════════════════════════════════════════
-- 12. ROW LEVEL SECURITY — Enable + Policies
--     (outside transaction to avoid partial RLS on failure)
-- ═══════════════════════════════════════════════════════════════

-- ── Enable RLS on ALL tables ──────────────────────────────────

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_pnl ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pnl_timeseries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.option_chain_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.features_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experiment_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.config ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_fills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_holdings_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_cash_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_candles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_tickers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_indicators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_reconciliation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_notional ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_gameplans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_gameplan_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_pivots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.technical_trendlines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.technical_levels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.structure_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bounce_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bounce_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pnl_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.thoughts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_heartbeat ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.copilot_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.boot_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_snapshot_focus ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_snapshot_scout ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_sparkline_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mover_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_focus_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cash_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fee_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trade_locks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_regimes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ef_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zoe_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_reconciliation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zoe_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.config_audit_log ENABLE ROW LEVEL SECURITY;


-- ── DROP all policies first (idempotent) ──────────────────────

-- v4 base
DROP POLICY IF EXISTS "anon_read_users" ON public.users;
DROP POLICY IF EXISTS "service_all_users" ON public.users;
DROP POLICY IF EXISTS "anon_read_accounts" ON public.accounts;
DROP POLICY IF EXISTS "service_all_accounts" ON public.accounts;
DROP POLICY IF EXISTS "anon_read_daily_pnl" ON public.daily_pnl;
DROP POLICY IF EXISTS "service_all_daily_pnl" ON public.daily_pnl;
DROP POLICY IF EXISTS "allow_public_read_daily_pnl" ON public.daily_pnl;
DROP POLICY IF EXISTS "anon_read_trades" ON public.trades;
DROP POLICY IF EXISTS "service_all_trades" ON public.trades;
DROP POLICY IF EXISTS "allow_public_read_trades" ON public.trades;
DROP POLICY IF EXISTS "anon_read_orders" ON public.orders;
DROP POLICY IF EXISTS "service_all_orders" ON public.orders;
DROP POLICY IF EXISTS "anon_read_fills" ON public.fills;
DROP POLICY IF EXISTS "service_all_fills" ON public.fills;
DROP POLICY IF EXISTS "anon_read_positions" ON public.positions;
DROP POLICY IF EXISTS "service_all_positions" ON public.positions;
DROP POLICY IF EXISTS "allow_public_read_positions" ON public.positions;
DROP POLICY IF EXISTS "anon_read_pnl_timeseries" ON public.pnl_timeseries;
DROP POLICY IF EXISTS "service_all_pnl_timeseries" ON public.pnl_timeseries;
DROP POLICY IF EXISTS "anon_read_option_chain_snapshots" ON public.option_chain_snapshots;
DROP POLICY IF EXISTS "service_all_option_chain_snapshots" ON public.option_chain_snapshots;
DROP POLICY IF EXISTS "anon_read_research_items" ON public.research_items;
DROP POLICY IF EXISTS "service_all_research_items" ON public.research_items;
DROP POLICY IF EXISTS "anon_read_features_daily" ON public.features_daily;
DROP POLICY IF EXISTS "service_all_features_daily" ON public.features_daily;
DROP POLICY IF EXISTS "anon_read_strategy_registry" ON public.strategy_registry;
DROP POLICY IF EXISTS "service_all_strategy_registry" ON public.strategy_registry;
DROP POLICY IF EXISTS "anon_read_experiment_runs" ON public.experiment_runs;
DROP POLICY IF EXISTS "service_all_experiment_runs" ON public.experiment_runs;
DROP POLICY IF EXISTS "anon_read_health_reports" ON public.health_reports;
DROP POLICY IF EXISTS "service_all_health_reports" ON public.health_reports;
DROP POLICY IF EXISTS "anon_read_health_events" ON public.health_events;
DROP POLICY IF EXISTS "service_all_health_events" ON public.health_events;
DROP POLICY IF EXISTS "anon_read_audit_log" ON public.audit_log;
DROP POLICY IF EXISTS "service_all_audit_log" ON public.audit_log;
DROP POLICY IF EXISTS "anon_read_config" ON public.config;
DROP POLICY IF EXISTS "service_all_config" ON public.config;

-- crypto core
DROP POLICY IF EXISTS "anon_read" ON public.crypto_orders;
DROP POLICY IF EXISTS "service_all" ON public.crypto_orders;
DROP POLICY IF EXISTS "anon_read_crypto_orders" ON public.crypto_orders;
DROP POLICY IF EXISTS "service_all_crypto_orders" ON public.crypto_orders;
DROP POLICY IF EXISTS "anon_read" ON public.crypto_fills;
DROP POLICY IF EXISTS "service_all" ON public.crypto_fills;
DROP POLICY IF EXISTS "anon_read_crypto_fills" ON public.crypto_fills;
DROP POLICY IF EXISTS "service_all_crypto_fills" ON public.crypto_fills;
DROP POLICY IF EXISTS "anon_read_crypto_positions" ON public.crypto_positions;
DROP POLICY IF EXISTS "service_all_crypto_positions" ON public.crypto_positions;
DROP POLICY IF EXISTS "anon_read" ON public.crypto_holdings_snapshots;
DROP POLICY IF EXISTS "service_all" ON public.crypto_holdings_snapshots;
DROP POLICY IF EXISTS "anon_read_crypto_holdings_snapshots" ON public.crypto_holdings_snapshots;
DROP POLICY IF EXISTS "service_all_crypto_holdings_snapshots" ON public.crypto_holdings_snapshots;
DROP POLICY IF EXISTS "anon_read" ON public.crypto_cash_snapshots;
DROP POLICY IF EXISTS "service_all" ON public.crypto_cash_snapshots;
DROP POLICY IF EXISTS "anon_read_crypto_cash_snapshots" ON public.crypto_cash_snapshots;
DROP POLICY IF EXISTS "service_all_crypto_cash_snapshots" ON public.crypto_cash_snapshots;
DROP POLICY IF EXISTS "anon_read" ON public.crypto_candles;
DROP POLICY IF EXISTS "service_all" ON public.crypto_candles;
DROP POLICY IF EXISTS "Allow public read" ON public.crypto_candles;
DROP POLICY IF EXISTS "Allow service insert/update" ON public.crypto_candles;
DROP POLICY IF EXISTS "anon_read_crypto_candles" ON public.crypto_candles;
DROP POLICY IF EXISTS "service_all_crypto_candles" ON public.crypto_candles;
DROP POLICY IF EXISTS "anon_read" ON public.crypto_tickers;
DROP POLICY IF EXISTS "service_all" ON public.crypto_tickers;
DROP POLICY IF EXISTS "anon_read_crypto_tickers" ON public.crypto_tickers;
DROP POLICY IF EXISTS "service_all_crypto_tickers" ON public.crypto_tickers;
DROP POLICY IF EXISTS "anon_read_crypto_indicators" ON public.crypto_indicators;
DROP POLICY IF EXISTS "service_all_crypto_indicators" ON public.crypto_indicators;
DROP POLICY IF EXISTS "anon_read" ON public.crypto_audit_log;
DROP POLICY IF EXISTS "service_all" ON public.crypto_audit_log;
DROP POLICY IF EXISTS "anon_read_crypto_audit_log" ON public.crypto_audit_log;
DROP POLICY IF EXISTS "service_all_crypto_audit_log" ON public.crypto_audit_log;
DROP POLICY IF EXISTS "anon_read" ON public.crypto_reconciliation_events;
DROP POLICY IF EXISTS "service_all" ON public.crypto_reconciliation_events;
DROP POLICY IF EXISTS "anon_read_crypto_reconciliation_events" ON public.crypto_reconciliation_events;
DROP POLICY IF EXISTS "service_all_crypto_reconciliation_events" ON public.crypto_reconciliation_events;
DROP POLICY IF EXISTS "anon_read" ON public.daily_notional;
DROP POLICY IF EXISTS "service_all" ON public.daily_notional;
DROP POLICY IF EXISTS "anon_read_daily_notional" ON public.daily_notional;
DROP POLICY IF EXISTS "service_all_daily_notional" ON public.daily_notional;
DROP POLICY IF EXISTS "anon_read" ON public.daily_gameplans;
DROP POLICY IF EXISTS "service_all" ON public.daily_gameplans;
DROP POLICY IF EXISTS "allow_public_read_gameplans" ON public.daily_gameplans;
DROP POLICY IF EXISTS "anon_read_daily_gameplans" ON public.daily_gameplans;
DROP POLICY IF EXISTS "service_all_daily_gameplans" ON public.daily_gameplans;
DROP POLICY IF EXISTS "anon_read" ON public.daily_gameplan_items;
DROP POLICY IF EXISTS "service_all" ON public.daily_gameplan_items;
DROP POLICY IF EXISTS "allow_public_read_gameplan_items" ON public.daily_gameplan_items;
DROP POLICY IF EXISTS "anon_read_daily_gameplan_items" ON public.daily_gameplan_items;
DROP POLICY IF EXISTS "service_all_daily_gameplan_items" ON public.daily_gameplan_items;

-- trendlines + bounce
DROP POLICY IF EXISTS "anon_read_market_pivots" ON public.market_pivots;
DROP POLICY IF EXISTS "service_all_market_pivots" ON public.market_pivots;
DROP POLICY IF EXISTS "anon_read_technical_trendlines" ON public.technical_trendlines;
DROP POLICY IF EXISTS "service_all_technical_trendlines" ON public.technical_trendlines;
DROP POLICY IF EXISTS "anon_read_technical_levels" ON public.technical_levels;
DROP POLICY IF EXISTS "service_all_technical_levels" ON public.technical_levels;
DROP POLICY IF EXISTS "anon_read_structure_events" ON public.structure_events;
DROP POLICY IF EXISTS "service_all_structure_events" ON public.structure_events;
DROP POLICY IF EXISTS "anon_read_bounce_events" ON public.bounce_events;
DROP POLICY IF EXISTS "service_all_bounce_events" ON public.bounce_events;
DROP POLICY IF EXISTS "anon_read_bounce_intents" ON public.bounce_intents;
DROP POLICY IF EXISTS "service_all_bounce_intents" ON public.bounce_intents;

-- pnl_daily, candidate_scans, thoughts, health_heartbeat
DROP POLICY IF EXISTS "anon_read_pnl_daily" ON public.pnl_daily;
DROP POLICY IF EXISTS "service_all_pnl_daily" ON public.pnl_daily;
DROP POLICY IF EXISTS "anon_read_candidate_scans" ON public.candidate_scans;
DROP POLICY IF EXISTS "service_all_candidate_scans" ON public.candidate_scans;
DROP POLICY IF EXISTS "anon_read_thoughts" ON public.thoughts;
DROP POLICY IF EXISTS "service_all_thoughts" ON public.thoughts;
DROP POLICY IF EXISTS "anon_read_health_heartbeat" ON public.health_heartbeat;
DROP POLICY IF EXISTS "service_all_health_heartbeat" ON public.health_heartbeat;
DROP POLICY IF EXISTS "anon_read_risk_events" ON public.risk_events;
DROP POLICY IF EXISTS "service_all_risk_events" ON public.risk_events;

-- copilot
DROP POLICY IF EXISTS "anon_read_copilot_messages" ON public.copilot_messages;
DROP POLICY IF EXISTS "anon_insert_copilot_messages" ON public.copilot_messages;
DROP POLICY IF EXISTS "service_all_copilot_messages" ON public.copilot_messages;

-- boot
DROP POLICY IF EXISTS "allow_anon_read_agent_state" ON public.agent_state;
DROP POLICY IF EXISTS "allow_service_all_agent_state" ON public.agent_state;
DROP POLICY IF EXISTS "anon_read_agent_state" ON public.agent_state;
DROP POLICY IF EXISTS "service_all_agent_state" ON public.agent_state;
DROP POLICY IF EXISTS "allow_anon_read_boot_audit" ON public.boot_audit;
DROP POLICY IF EXISTS "allow_service_all_boot_audit" ON public.boot_audit;
DROP POLICY IF EXISTS "anon_read_boot_audit" ON public.boot_audit;
DROP POLICY IF EXISTS "service_all_boot_audit" ON public.boot_audit;

-- market data
DROP POLICY IF EXISTS "market_catalog_read" ON public.market_catalog;
DROP POLICY IF EXISTS "market_catalog_write" ON public.market_catalog;
DROP POLICY IF EXISTS "anon_read_market_catalog" ON public.market_catalog;
DROP POLICY IF EXISTS "service_all_market_catalog" ON public.market_catalog;
DROP POLICY IF EXISTS "market_focus_read" ON public.market_snapshot_focus;
DROP POLICY IF EXISTS "market_focus_write" ON public.market_snapshot_focus;
DROP POLICY IF EXISTS "anon_read_market_snapshot_focus" ON public.market_snapshot_focus;
DROP POLICY IF EXISTS "service_all_market_snapshot_focus" ON public.market_snapshot_focus;
DROP POLICY IF EXISTS "market_scout_read" ON public.market_snapshot_scout;
DROP POLICY IF EXISTS "market_scout_write" ON public.market_snapshot_scout;
DROP POLICY IF EXISTS "anon_read_market_snapshot_scout" ON public.market_snapshot_scout;
DROP POLICY IF EXISTS "service_all_market_snapshot_scout" ON public.market_snapshot_scout;
DROP POLICY IF EXISTS "sparkline_read" ON public.market_sparkline_points;
DROP POLICY IF EXISTS "sparkline_write" ON public.market_sparkline_points;
DROP POLICY IF EXISTS "anon_read_market_sparkline_points" ON public.market_sparkline_points;
DROP POLICY IF EXISTS "service_all_market_sparkline_points" ON public.market_sparkline_points;
DROP POLICY IF EXISTS "movers_read" ON public.mover_events;
DROP POLICY IF EXISTS "movers_write" ON public.mover_events;
DROP POLICY IF EXISTS "anon_read_mover_events" ON public.mover_events;
DROP POLICY IF EXISTS "service_all_mover_events" ON public.mover_events;
DROP POLICY IF EXISTS "focus_config_read" ON public.market_focus_config;
DROP POLICY IF EXISTS "focus_config_write" ON public.market_focus_config;
DROP POLICY IF EXISTS "anon_read_market_focus_config" ON public.market_focus_config;
DROP POLICY IF EXISTS "service_all_market_focus_config" ON public.market_focus_config;

-- accounting
DROP POLICY IF EXISTS "anon_read_cash_events" ON public.cash_events;
DROP POLICY IF EXISTS "service_all_cash_events" ON public.cash_events;
DROP POLICY IF EXISTS "anon_read_fee_ledger" ON public.fee_ledger;
DROP POLICY IF EXISTS "service_all_fee_ledger" ON public.fee_ledger;

-- order lifecycle
DROP POLICY IF EXISTS "anon_read_order_intents" ON public.order_intents;
DROP POLICY IF EXISTS "service_all_order_intents" ON public.order_intents;
DROP POLICY IF EXISTS "anon_read_order_events" ON public.order_events;
DROP POLICY IF EXISTS "service_all_order_events" ON public.order_events;
DROP POLICY IF EXISTS "anon_read_trade_locks" ON public.trade_locks;
DROP POLICY IF EXISTS "service_all_trade_locks" ON public.trade_locks;

-- ef tables
DROP POLICY IF EXISTS "anon_read_ef_features" ON public.ef_features;
DROP POLICY IF EXISTS "service_all_ef_features" ON public.ef_features;
DROP POLICY IF EXISTS "anon_read_ef_regimes" ON public.ef_regimes;
DROP POLICY IF EXISTS "service_all_ef_regimes" ON public.ef_regimes;
DROP POLICY IF EXISTS "anon_read_ef_signals" ON public.ef_signals;
DROP POLICY IF EXISTS "service_all_ef_signals" ON public.ef_signals;
DROP POLICY IF EXISTS "anon_read_ef_positions" ON public.ef_positions;
DROP POLICY IF EXISTS "service_all_ef_positions" ON public.ef_positions;
DROP POLICY IF EXISTS "anon_read_ef_state" ON public.ef_state;
DROP POLICY IF EXISTS "service_all_ef_state" ON public.ef_state;

-- zoe events / health / broker reconciliation
DROP POLICY IF EXISTS "anon_read_zoe_health" ON public.zoe_health;
DROP POLICY IF EXISTS "service_all_zoe_health" ON public.zoe_health;
DROP POLICY IF EXISTS "anon_read_broker_reconciliation" ON public.broker_reconciliation;
DROP POLICY IF EXISTS "service_all_broker_reconciliation" ON public.broker_reconciliation;
DROP POLICY IF EXISTS "anon_read_zoe_events" ON public.zoe_events;
DROP POLICY IF EXISTS "service_all_zoe_events" ON public.zoe_events;

-- config versioning
DROP POLICY IF EXISTS "anon_read_strategy_configs" ON public.strategy_configs;
DROP POLICY IF EXISTS "service_all_strategy_configs" ON public.strategy_configs;
DROP POLICY IF EXISTS "anon_read_config_audit_log" ON public.config_audit_log;
DROP POLICY IF EXISTS "service_all_config_audit_log" ON public.config_audit_log;


-- ── CREATE policies: public read + service_role write ─────────

-- v4 base tables
CREATE POLICY "anon_read_users" ON public.users FOR SELECT USING (true);
CREATE POLICY "service_all_users" ON public.users FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_accounts" ON public.accounts FOR SELECT USING (true);
CREATE POLICY "service_all_accounts" ON public.accounts FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_daily_pnl" ON public.daily_pnl FOR SELECT USING (true);
CREATE POLICY "service_all_daily_pnl" ON public.daily_pnl FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_trades" ON public.trades FOR SELECT USING (true);
CREATE POLICY "service_all_trades" ON public.trades FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_orders" ON public.orders FOR SELECT USING (true);
CREATE POLICY "service_all_orders" ON public.orders FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_fills" ON public.fills FOR SELECT USING (true);
CREATE POLICY "service_all_fills" ON public.fills FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_positions" ON public.positions FOR SELECT USING (true);
CREATE POLICY "service_all_positions" ON public.positions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_pnl_timeseries" ON public.pnl_timeseries FOR SELECT USING (true);
CREATE POLICY "service_all_pnl_timeseries" ON public.pnl_timeseries FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_option_chain_snapshots" ON public.option_chain_snapshots FOR SELECT USING (true);
CREATE POLICY "service_all_option_chain_snapshots" ON public.option_chain_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_research_items" ON public.research_items FOR SELECT USING (true);
CREATE POLICY "service_all_research_items" ON public.research_items FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_features_daily" ON public.features_daily FOR SELECT USING (true);
CREATE POLICY "service_all_features_daily" ON public.features_daily FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_strategy_registry" ON public.strategy_registry FOR SELECT USING (true);
CREATE POLICY "service_all_strategy_registry" ON public.strategy_registry FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_experiment_runs" ON public.experiment_runs FOR SELECT USING (true);
CREATE POLICY "service_all_experiment_runs" ON public.experiment_runs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_health_reports" ON public.health_reports FOR SELECT USING (true);
CREATE POLICY "service_all_health_reports" ON public.health_reports FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_health_events" ON public.health_events FOR SELECT USING (true);
CREATE POLICY "service_all_health_events" ON public.health_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_audit_log" ON public.audit_log FOR SELECT USING (true);
CREATE POLICY "service_all_audit_log" ON public.audit_log FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_config" ON public.config FOR SELECT USING (true);
CREATE POLICY "service_all_config" ON public.config FOR ALL TO service_role USING (true) WITH CHECK (true);

-- crypto core
CREATE POLICY "anon_read_crypto_orders" ON public.crypto_orders FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_orders" ON public.crypto_orders FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_fills" ON public.crypto_fills FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_fills" ON public.crypto_fills FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_positions" ON public.crypto_positions FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_positions" ON public.crypto_positions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_holdings_snapshots" ON public.crypto_holdings_snapshots FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_holdings_snapshots" ON public.crypto_holdings_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_cash_snapshots" ON public.crypto_cash_snapshots FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_cash_snapshots" ON public.crypto_cash_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_candles" ON public.crypto_candles FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_candles" ON public.crypto_candles FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_tickers" ON public.crypto_tickers FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_tickers" ON public.crypto_tickers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_indicators" ON public.crypto_indicators FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_indicators" ON public.crypto_indicators FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_audit_log" ON public.crypto_audit_log FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_audit_log" ON public.crypto_audit_log FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_crypto_reconciliation_events" ON public.crypto_reconciliation_events FOR SELECT USING (true);
CREATE POLICY "service_all_crypto_reconciliation_events" ON public.crypto_reconciliation_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_daily_notional" ON public.daily_notional FOR SELECT USING (true);
CREATE POLICY "service_all_daily_notional" ON public.daily_notional FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_daily_gameplans" ON public.daily_gameplans FOR SELECT USING (true);
CREATE POLICY "service_all_daily_gameplans" ON public.daily_gameplans FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_daily_gameplan_items" ON public.daily_gameplan_items FOR SELECT USING (true);
CREATE POLICY "service_all_daily_gameplan_items" ON public.daily_gameplan_items FOR ALL TO service_role USING (true) WITH CHECK (true);

-- trendlines + bounce
CREATE POLICY "anon_read_market_pivots" ON public.market_pivots FOR SELECT USING (true);
CREATE POLICY "service_all_market_pivots" ON public.market_pivots FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_technical_trendlines" ON public.technical_trendlines FOR SELECT USING (true);
CREATE POLICY "service_all_technical_trendlines" ON public.technical_trendlines FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_technical_levels" ON public.technical_levels FOR SELECT USING (true);
CREATE POLICY "service_all_technical_levels" ON public.technical_levels FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_structure_events" ON public.structure_events FOR SELECT USING (true);
CREATE POLICY "service_all_structure_events" ON public.structure_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_bounce_events" ON public.bounce_events FOR SELECT USING (true);
CREATE POLICY "service_all_bounce_events" ON public.bounce_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_bounce_intents" ON public.bounce_intents FOR SELECT USING (true);
CREATE POLICY "service_all_bounce_intents" ON public.bounce_intents FOR ALL TO service_role USING (true) WITH CHECK (true);

-- pnl_daily, candidate_scans, thoughts, health_heartbeat, risk_events
CREATE POLICY "anon_read_pnl_daily" ON public.pnl_daily FOR SELECT USING (true);
CREATE POLICY "service_all_pnl_daily" ON public.pnl_daily FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_candidate_scans" ON public.candidate_scans FOR SELECT USING (true);
CREATE POLICY "service_all_candidate_scans" ON public.candidate_scans FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_thoughts" ON public.thoughts FOR SELECT USING (true);
CREATE POLICY "service_all_thoughts" ON public.thoughts FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_health_heartbeat" ON public.health_heartbeat FOR SELECT USING (true);
CREATE POLICY "service_all_health_heartbeat" ON public.health_heartbeat FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_risk_events" ON public.risk_events FOR SELECT USING (true);
CREATE POLICY "service_all_risk_events" ON public.risk_events FOR ALL TO service_role USING (true) WITH CHECK (true);

-- copilot (anon can read + insert)
CREATE POLICY "anon_read_copilot_messages" ON public.copilot_messages FOR SELECT USING (true);
CREATE POLICY "anon_insert_copilot_messages" ON public.copilot_messages FOR INSERT WITH CHECK (true);
CREATE POLICY "service_all_copilot_messages" ON public.copilot_messages FOR ALL TO service_role USING (true) WITH CHECK (true);

-- boot reconciliation
CREATE POLICY "anon_read_agent_state" ON public.agent_state FOR SELECT USING (true);
CREATE POLICY "service_all_agent_state" ON public.agent_state FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_boot_audit" ON public.boot_audit FOR SELECT USING (true);
CREATE POLICY "service_all_boot_audit" ON public.boot_audit FOR ALL TO service_role USING (true) WITH CHECK (true);

-- market data (6 tables)
CREATE POLICY "anon_read_market_catalog" ON public.market_catalog FOR SELECT USING (true);
CREATE POLICY "service_all_market_catalog" ON public.market_catalog FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_market_snapshot_focus" ON public.market_snapshot_focus FOR SELECT USING (true);
CREATE POLICY "service_all_market_snapshot_focus" ON public.market_snapshot_focus FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_market_snapshot_scout" ON public.market_snapshot_scout FOR SELECT USING (true);
CREATE POLICY "service_all_market_snapshot_scout" ON public.market_snapshot_scout FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_market_sparkline_points" ON public.market_sparkline_points FOR SELECT USING (true);
CREATE POLICY "service_all_market_sparkline_points" ON public.market_sparkline_points FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_mover_events" ON public.mover_events FOR SELECT USING (true);
CREATE POLICY "service_all_mover_events" ON public.mover_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_market_focus_config" ON public.market_focus_config FOR SELECT USING (true);
CREATE POLICY "service_all_market_focus_config" ON public.market_focus_config FOR ALL TO service_role USING (true) WITH CHECK (true);

-- accounting
CREATE POLICY "anon_read_cash_events" ON public.cash_events FOR SELECT USING (true);
CREATE POLICY "service_all_cash_events" ON public.cash_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_fee_ledger" ON public.fee_ledger FOR SELECT USING (true);
CREATE POLICY "service_all_fee_ledger" ON public.fee_ledger FOR ALL TO service_role USING (true) WITH CHECK (true);

-- order lifecycle
CREATE POLICY "anon_read_order_intents" ON public.order_intents FOR SELECT USING (true);
CREATE POLICY "service_all_order_intents" ON public.order_intents FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_order_events" ON public.order_events FOR SELECT USING (true);
CREATE POLICY "service_all_order_events" ON public.order_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_trade_locks" ON public.trade_locks FOR SELECT USING (true);
CREATE POLICY "service_all_trade_locks" ON public.trade_locks FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Edge Factory (ef_*) — backend-only (service_role only, no anon read)
CREATE POLICY "service_all_ef_features" ON public.ef_features FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all_ef_regimes" ON public.ef_regimes FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all_ef_signals" ON public.ef_signals FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all_ef_positions" ON public.ef_positions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all_ef_state" ON public.ef_state FOR ALL TO service_role USING (true) WITH CHECK (true);

-- zoe events / health / broker reconciliation
CREATE POLICY "anon_read_zoe_health" ON public.zoe_health FOR SELECT USING (true);
CREATE POLICY "service_all_zoe_health" ON public.zoe_health FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_broker_reconciliation" ON public.broker_reconciliation FOR SELECT USING (true);
CREATE POLICY "service_all_broker_reconciliation" ON public.broker_reconciliation FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_zoe_events" ON public.zoe_events FOR SELECT USING (true);
CREATE POLICY "service_all_zoe_events" ON public.zoe_events FOR ALL TO service_role USING (true) WITH CHECK (true);

-- config versioning
CREATE POLICY "anon_read_strategy_configs" ON public.strategy_configs FOR SELECT USING (true);
CREATE POLICY "service_all_strategy_configs" ON public.strategy_configs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "anon_read_config_audit_log" ON public.config_audit_log FOR SELECT USING (true);
CREATE POLICY "service_all_config_audit_log" ON public.config_audit_log FOR ALL TO service_role USING (true) WITH CHECK (true);


-- ═══════════════════════════════════════════════════════════════
-- 13. VIEWS (compact mobile views)
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_positions_compact AS
SELECT
    h.mode,
    h.taken_at,
    h.holdings,
    h.total_crypto_value
FROM crypto_holdings_snapshots h
INNER JOIN (
    SELECT mode, MAX(taken_at) AS max_taken
    FROM crypto_holdings_snapshots
    GROUP BY mode
) latest ON h.mode = latest.mode AND h.taken_at = latest.max_taken;

CREATE OR REPLACE VIEW v_scanner_latest AS
SELECT cs.*
FROM candidate_scans cs
INNER JOIN (
    SELECT mode, MAX(created_at) AS max_created
    FROM candidate_scans
    GROUP BY mode
) latest ON cs.mode = latest.mode AND cs.created_at = latest.max_created;

CREATE OR REPLACE VIEW v_pnl_timeseries AS
SELECT
    mode,
    date_trunc('hour', taken_at) +
        (EXTRACT(minute FROM taken_at)::int / 5) * INTERVAL '5 minutes' AS bucket,
    MAX(buying_power) AS buying_power,
    MAX(cash_available) AS cash_available,
    MAX(taken_at) AS latest_at
FROM crypto_cash_snapshots
WHERE taken_at > NOW() - INTERVAL '90 days'
GROUP BY mode, bucket
ORDER BY mode, bucket;


-- ═══════════════════════════════════════════════════════════════
-- 14. RPC FUNCTIONS
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION get_latest_scan_batch(p_mode TEXT)
RETURNS SETOF candidate_scans
LANGUAGE sql
STABLE
AS $$
    SELECT cs.*
    FROM candidate_scans cs
    WHERE cs.mode = p_mode
        AND cs.created_at = (
            SELECT MAX(created_at)
            FROM candidate_scans
            WHERE mode = p_mode
        )
    ORDER BY cs.score DESC;
$$;

GRANT EXECUTE ON FUNCTION get_latest_scan_batch(TEXT) TO anon;
GRANT EXECUTE ON FUNCTION get_latest_scan_batch(TEXT) TO authenticated;


-- ═══════════════════════════════════════════════════════════════
-- 15. GRANTS
-- ═══════════════════════════════════════════════════════════════

GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO anon, authenticated;

-- Extra grants for specific tables
GRANT SELECT ON public.agent_state TO anon, authenticated;
GRANT ALL ON public.agent_state TO service_role;
GRANT SELECT ON public.boot_audit TO anon, authenticated;
GRANT ALL ON public.boot_audit TO service_role;

-- Revoke write from anon on critical trading tables
REVOKE INSERT, UPDATE, DELETE ON public.crypto_orders FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.crypto_fills FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.crypto_cash_snapshots FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.crypto_holdings_snapshots FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.crypto_reconciliation_events FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.daily_notional FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.ef_features FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.ef_regimes FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.ef_signals FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.ef_positions FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.ef_state FROM anon;


-- ═══════════════════════════════════════════════════════════════
-- 16. POSTGREST SCHEMA CACHE RELOAD
-- ═══════════════════════════════════════════════════════════════

NOTIFY pgrst, 'reload schema';
NOTIFY pgrst, 'reload config';
