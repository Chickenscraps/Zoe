-- 20260211_crypto_prod.sql
-- Production schema for Robinhood Crypto Module
-- Enable UUID extension if not enabled
create extension if not exists "uuid-ossp";
-- 1. Orders (Enhanced)
create table if not exists crypto_orders (
    id uuid primary key default uuid_generate_v4(),
    client_order_id text unique not null,
    symbol text not null,
    side text not null check (side in ('buy', 'sell')),
    order_type text not null default 'market',
    qty numeric,
    notional numeric,
    limit_price numeric,
    status text not null default 'pending',
    -- pending, submitted, live, filled, canceled, rejected
    filled_qty numeric default 0,
    filled_avg_price numeric default 0,
    fees numeric default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    raw_response jsonb
);
-- 2. Fills (Immutable Ledger)
create table if not exists crypto_fills (
    fill_id text primary key,
    -- External ID from RH
    order_id uuid references crypto_orders(id),
    symbol text not null,
    side text not null,
    qty numeric not null,
    price numeric not null,
    fee numeric default 0,
    executed_at timestamptz not null,
    created_at timestamptz default now()
);
-- 3. Positions (Live State)
create table if not exists crypto_positions (
    symbol text primary key,
    qty numeric not null default 0,
    avg_cost numeric not null default 0,
    current_price numeric,
    market_value numeric,
    unrealized_pnl numeric,
    unrealized_pnl_pct numeric,
    last_updated_at timestamptz default now()
);
-- 4. Candles (OHLCV)
create table if not exists crypto_candles (
    symbol text not null,
    timeframe text not null,
    -- '1m', '5m', '1h', '1d'
    bucket timestamptz not null,
    open numeric not null,
    high numeric not null,
    low numeric not null,
    close numeric not null,
    volume numeric default 0,
    is_final boolean default false,
    primary key (symbol, timeframe, bucket)
);
-- 5. Indicators (Derived Data)
create table if not exists crypto_indicators (
    symbol text not null,
    timeframe text not null,
    bucket timestamptz not null,
    sma_50 numeric,
    sma_200 numeric,
    rsi_14 numeric,
    regime text,
    -- 'bull', 'bear', 'neutral'
    signal text,
    -- 'buy', 'sell', 'hold'
    created_at timestamptz default now(),
    primary key (symbol, timeframe, bucket)
);
-- 6. Audit Log (Decision Trail)
create table if not exists crypto_audit_log (
    id uuid primary key default uuid_generate_v4(),
    timestamp timestamptz default now(),
    component text not null,
    -- 'strategy', 'risk', 'broker', 'reconciler'
    event text not null,
    level text default 'info',
    details jsonb
);
-- 7. Daily Gameplans (For Reference)
create table if not exists daily_gameplans (
    id uuid primary key default uuid_generate_v4(),
    date date unique not null,
    status text default 'draft',
    instance_id text,
    created_at timestamptz default now()
);
create table if not exists daily_gameplan_items (
    id uuid primary key default uuid_generate_v4(),
    plan_id uuid references daily_gameplans(id) on delete cascade,
    symbol text not null,
    catalyst_summary text,
    regime text,
    ivr_tech_snapshot text,
    preferred_strategy text,
    risk_tier text,
    created_at timestamptz default now()
);
-- Indexes for performance
create index if not exists idx_crypto_orders_status on crypto_orders(status);
create index if not exists idx_crypto_candles_symbol_tf on crypto_candles(symbol, timeframe, bucket desc);
