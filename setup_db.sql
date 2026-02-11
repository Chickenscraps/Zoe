-- ZOE TERMINAL & TRADER - FULL DATABASE SETUP
-- Run this script in the Supabase SQL Editor to initialize your project.
-- ============================================================================
-- 1. EXTENSIONS
-- ============================================================================
create extension if not exists "uuid-ossp";
-- ============================================================================
-- 2. BASE TABLES (Users, Accounts, Trades) - from schema_v4_tables.sql
-- ============================================================================
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
    equity numeric(12, 2) default 0.00,
    cash numeric(12, 2) default 0.00,
    buying_power numeric(12, 2) default 0.00,
    pdt_count int default 0,
    day_trades_history jsonb default '[]'::jsonb,
    updated_at timestamptz default now()
);
-- Ensure Unique Constraint for safe upserts/seeding
CREATE UNIQUE INDEX IF NOT EXISTS accounts_user_instance_idx ON public.accounts (user_id, instance_id);
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
create table if not exists public.audit_log (
    id uuid primary key default uuid_generate_v4(),
    actor text default 'zoe',
    action text not null,
    details jsonb,
    timestamp timestamptz default now()
);
create table if not exists public.config (
    key text primary key,
    value text,
    updated_at timestamptz default now()
);
-- ============================================================================
-- 3. CRYPTO TABLES - from migrations/20260211_full_setup.sql
-- ============================================================================
CREATE TABLE IF NOT EXISTS crypto_orders (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_order_id text UNIQUE NOT NULL,
    symbol text NOT NULL,
    side text NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type text NOT NULL DEFAULT 'market',
    qty numeric,
    notional numeric,
    limit_price numeric,
    status text NOT NULL DEFAULT 'pending',
    filled_qty numeric DEFAULT 0,
    filled_avg_price numeric DEFAULT 0,
    fees numeric DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    raw_response jsonb
);
CREATE TABLE IF NOT EXISTS crypto_cash_snapshots (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    cash_available numeric NOT NULL,
    buying_power numeric NOT NULL,
    taken_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS crypto_holdings_snapshots (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    holdings jsonb NOT NULL,
    total_crypto_value numeric NOT NULL DEFAULT 0,
    taken_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS crypto_candles (
    symbol text NOT NULL,
    timeframe text NOT NULL,
    bucket timestamptz NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric DEFAULT 0,
    is_final boolean DEFAULT false,
    PRIMARY KEY (symbol, timeframe, bucket)
);
-- ============================================================================
-- 4. RPC FUNCTIONS - from schema_v4_rpc.sql
-- ============================================================================
create or replace function public.get_account_overview(p_discord_id text default null) returns table (
        account_id uuid,
        equity numeric,
        cash numeric,
        buying_power numeric,
        pdt_count int,
        day_pnl numeric,
        last_updated timestamptz
    ) language plpgsql security definer as $$
declare v_user_id uuid;
v_account_id uuid;
begin if p_discord_id is not null then
select id into v_user_id
from public.users
where discord_id = p_discord_id;
else
select id into v_user_id
from public.users
limit 1;
end if;
select id into v_account_id
from public.accounts
where user_id = v_user_id
order by updated_at desc
limit 1;
return query
select a.id,
    a.equity,
    a.cash,
    a.buying_power,
    a.pdt_count,
    coalesce(d.realized_pnl + d.unrealized_pnl, 0.0) as day_pnl,
    a.updated_at
from public.accounts a
    left join public.daily_pnl d on d.account_id = a.id
    and d.date = current_date
where a.id = v_account_id;
end;
$$;
-- ============================================================================
-- 5. PERMISSIONS (RLS)
-- ============================================================================
-- Enable RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;
-- Simple Policies (Allow All for Anon/Service for now to prevent lockout)
CREATE POLICY "Enable read access for all users" ON public.users FOR
SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.accounts FOR
SELECT USING (true);
CREATE POLICY "Enable update for service role" ON public.accounts FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Enable insert for service role" ON public.accounts FOR
INSERT TO service_role WITH CHECK (true);
-- Grant usage
GRANT USAGE ON SCHEMA public TO postgres,
    anon,
    authenticated,
    service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres,
    anon,
    authenticated,
    service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres,
    anon,
    authenticated,
    service_role;
-- ============================================================================
-- 6. SEED DATA - from seed_v4.sql
-- ============================================================================
-- 1. Create/Ensure User (Josh / Chickenscraps)
insert into public.users (discord_id, username)
values ('292890243852664855', 'Chickenscraps') on conflict (discord_id) do nothing;
-- 2. Create/Ensure Account
do $$
declare v_user_id uuid;
v_account_id uuid;
begin
select id into v_user_id
from public.users
where discord_id = '292890243852664855';
if v_user_id is not null then
insert into public.accounts (user_id, instance_id, equity, cash, buying_power)
values (v_user_id, 'default', 2000.00, 2000.00, 2000.00) on conflict (user_id, instance_id) do nothing;
end if;
end $$;
