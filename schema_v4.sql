-- ZOE V4 SUPABASE SCHEMA (Idempotent)
-- Run this in the Supabase SQL Editor.
-- Enable extensions
create extension if not exists "uuid-ossp";
-- ============================================================
-- 1. USERS & PROFILES
-- ============================================================
create table if not exists public.users (
    id uuid primary key default uuid_generate_v4(),
    discord_id text unique not null,
    username text,
    created_at timestamptz default now(),
    last_seen timestamptz default now()
);
-- ============================================================
-- 2. ACCOUNTS (Paper State)
-- ============================================================
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
-- ============================================================
-- 3. DAILY STATS
-- ============================================================
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
-- Idempotent Index
create unique index if not exists daily_pnl_account_date_idx on public.daily_pnl(account_id, date);
-- ============================================================
-- 4. TRADES
-- ============================================================
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
-- ============================================================
-- 5. ORDERS
-- ============================================================
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
-- ============================================================
-- 6. FILLS
-- ============================================================
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
-- ============================================================
-- 7. POSITIONS
-- ============================================================
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
create unique index if not exists positions_account_symbol_idx on public.positions(account_id, symbol);
-- ============================================================
-- 8. ARTIFACTS
-- ============================================================
create table if not exists public.artifacts (
    id uuid primary key default uuid_generate_v4(),
    account_id uuid references public.accounts(id),
    kind text default 'image',
    source text not null,
    path text,
    metadata jsonb,
    created_at timestamptz default now()
);
-- ============================================================
-- 9. AUDIT & CONFIG
-- ============================================================
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
-- ============================================================
-- 10. DAILY GAMEPLANS
-- ============================================================
create table if not exists public.daily_gameplans (
    id uuid primary key default uuid_generate_v4(),
    instance_id text default 'default',
    date date not null default current_date,
    status text not null default 'draft',
    -- 'draft', 'refined', 'locked'
    created_at timestamptz default now(),
    unique(date, instance_id)
);
create table if not exists public.daily_gameplan_items (
    id uuid primary key default uuid_generate_v4(),
    plan_id uuid references public.daily_gameplans(id) on delete cascade,
    symbol text not null,
    catalyst_summary text,
    regime text,
    ivr_tech_snapshot text,
    preferred_strategy text,
    risk_tier text,
    do_not_trade boolean default false,
    visual_notes text,
    created_at timestamptz default now()
);
-- ============================================================
-- RLS POLICIES (Idempotent)
-- ============================================================
-- Enable RLS
alter table public.users enable row level security;
alter table public.accounts enable row level security;
alter table public.trades enable row level security;
alter table public.orders enable row level security;
alter table public.positions enable row level security;
-- Drop existing policies to ensure clean state (Idempotency)
drop policy if exists "allow_public_read_daily_pnl" on public.daily_pnl;
drop policy if exists "allow_public_read_trades" on public.trades;
drop policy if exists "allow_public_read_positions" on public.positions;
-- Re-create policies
create policy "allow_public_read_daily_pnl" on public.daily_pnl for
select using (true);
create policy "allow_public_read_trades" on public.trades for
select using (true);
create policy "allow_public_read_positions" on public.positions for
select using (true);
-- Gameplan Policies
alter table public.daily_gameplans enable row level security;
alter table public.daily_gameplan_items enable row level security;
drop policy if exists "allow_public_read_gameplans" on public.daily_gameplans;
drop policy if exists "allow_public_read_gameplan_items" on public.daily_gameplan_items;
create policy "allow_public_read_gameplans" on public.daily_gameplans for
select using (true);
create policy "allow_public_read_gameplan_items" on public.daily_gameplan_items for
select using (true);
