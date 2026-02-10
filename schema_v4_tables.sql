-- ZOE V4 PRO - STEP 1: TABLES
-- Run this FIRST. Ensure all tables are created successfully before running Step 2.
create extension if not exists "uuid-ossp";
-- 1. Users & Accounts
create table if not exists public.users (
    id uuid primary key default uuid_generate_v4(),
    discord_id text unique not null,
    username text,
    created_at timestamptz default now(),
    last_seen timestamptz default now()
);
create table if not exists public.accounts (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references public.users(id),
    instance_id text default 'default',
    equity numeric(12, 2) default 2000.00,
    cash numeric(12, 2) default 2000.00,
    buying_power numeric(12, 2) default 2000.00,
    pdt_count int default 0,
    day_trades_history jsonb default '[]'::jsonb,
    updated_at timestamptz default now()
);
-- 2. Performance Tracking
create table if not exists public.daily_pnl (
    id uuid primary key default uuid_generate_v4(),
    account_id uuid references public.accounts(id),
    date date default current_date,
    start_equity numeric(12, 2),
    end_equity numeric(12, 2),
    realized_pnl numeric(12, 2) default 0,
    unrealized_pnl numeric(12, 2) default 0,
    trades_count int default 0
);
-- 3. Trade Data
create table if not exists public.trades (
    id uuid primary key default uuid_generate_v4(),
    account_id uuid references public.accounts(id),
    symbol text not null,
    strategy text not null,
    status text default 'open',
    entry_time timestamptz default now(),
    exit_time timestamptz,
    entry_price numeric(12, 4),
    exit_price numeric(12, 4),
    quantity int default 1,
    pnl numeric(12, 2),
    score_at_entry jsonb,
    notes text
);
create table if not exists public.orders (
    id uuid primary key default uuid_generate_v4(),
    trade_id uuid references public.trades(id),
    account_id uuid references public.accounts(id),
    symbol text not null,
    side text not null,
    type text default 'limit',
    price numeric(12, 4),
    quantity int not null,
    status text default 'new',
    created_at timestamptz default now(),
    filled_at timestamptz,
    legs jsonb not null,
    meta jsonb
);
create table if not exists public.fills (
    id uuid primary key default uuid_generate_v4(),
    order_id uuid references public.orders(id),
    trade_id uuid references public.trades(id),
    timestamp timestamptz default now(),
    symbol text,
    side text,
    quantity int,
    price numeric(12, 4),
    fee numeric(12, 2) default 0
);
-- 4. Positions & Artifacts
DROP TABLE IF EXISTS public.positions CASCADE;
create table if not exists public.positions (
    id uuid primary key default uuid_generate_v4(),
    account_id uuid references public.accounts(id),
    symbol text not null,
    underlying text,
    quantity int default 0,
    avg_price numeric(12, 4),
    current_price numeric(12, 4),
    market_value numeric(12, 4),
    updated_at timestamptz default now()
);
create table if not exists public.artifacts (
    id uuid primary key default uuid_generate_v4(),
    account_id uuid references public.accounts(id),
    kind text default 'image',
    source text not null,
    path text,
    metadata jsonb,
    created_at timestamptz default now()
);
create table if not exists public.audit_log (
    id uuid primary key default uuid_generate_v4(),
    actor text default 'zoe',
    action text not null,
    details jsonb,
    timestamp timestamptz default now()
);
create table if not exists public.health_events (
    id uuid primary key default uuid_generate_v4(),
    component text not null,
    status text not null,
    message text,
    timestamp timestamptz default now()
);
create table if not exists public.config (
    key text primary key,
    value text,
    updated_at timestamptz default now()
);
