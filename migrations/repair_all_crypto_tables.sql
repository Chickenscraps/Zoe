-- repair_all_crypto_tables.sql
-- Run this in Supabase SQL Editor to fix ALL missing tables
-- ENABLE EXTENSIONS
create extension if not exists "uuid-ossp";
-- ---------------------------------------------------------
-- 1. ORDERS
-- ---------------------------------------------------------
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
    filled_qty numeric default 0,
    filled_avg_price numeric default 0,
    fees numeric default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    raw_response jsonb
);
-- ---------------------------------------------------------
-- 2. SNAPSHOTS (Cash & Holdings)
-- ---------------------------------------------------------
create table if not exists crypto_cash_snapshots (
    id uuid primary key default uuid_generate_v4(),
    cash_available numeric not null,
    buying_power numeric not null,
    taken_at timestamptz default now()
);
create table if not exists crypto_holdings_snapshots (
    id uuid primary key default uuid_generate_v4(),
    holdings jsonb not null,
    total_value numeric not null default 0,
    taken_at timestamptz default now()
);
-- ---------------------------------------------------------
-- 3. CANDLES (Market Data)
-- ---------------------------------------------------------
create table if not exists crypto_candles (
    symbol text not null,
    timeframe text not null,
    -- '1m', '5m', '1h'
    bucket timestamptz not null,
    open numeric not null,
    high numeric not null,
    low numeric not null,
    close numeric not null,
    volume numeric default 0,
    is_final boolean default false,
    primary key (symbol, timeframe, bucket)
);
-- ---------------------------------------------------------
-- 4. TICKERS (Live Prices)
-- ---------------------------------------------------------
create table if not exists crypto_tickers (
    symbol text primary key,
    price numeric not null,
    updated_at timestamptz default now()
);
-- ---------------------------------------------------------
-- 5. AUDIT & RECONCILIATION
-- ---------------------------------------------------------
create table if not exists crypto_audit_log (
    id uuid primary key default uuid_generate_v4(),
    timestamp timestamptz default now(),
    component text not null,
    event text not null,
    level text default 'info',
    details jsonb
);
create table if not exists crypto_reconciliation_events (
    id uuid primary key default uuid_generate_v4(),
    status text not null,
    reason text,
    taken_at timestamptz default now()
);
-- ---------------------------------------------------------
-- 6. DAILY PLANS
-- ---------------------------------------------------------
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
create table if not exists daily_notional (
    day date primary key default current_date,
    notional_used numeric default 0,
    last_updated timestamptz default now()
);
-- ---------------------------------------------------------
-- SECURITY POLICIES (RLS)
-- ---------------------------------------------------------
-- Enable RLS on all
alter table crypto_orders enable row level security;
alter table crypto_cash_snapshots enable row level security;
alter table crypto_holdings_snapshots enable row level security;
alter table crypto_candles enable row level security;
alter table crypto_tickers enable row level security;
alter table crypto_audit_log enable row level security;
alter table crypto_reconciliation_events enable row level security;
alter table daily_gameplans enable row level security;
alter table daily_gameplan_items enable row level security;
alter table daily_notional enable row level security;
-- Drop existing policies to prevent conflicts
drop policy if exists "Public read orders" on crypto_orders;
drop policy if exists "Public read snapshots" on crypto_cash_snapshots;
drop policy if exists "Public read holdings" on crypto_holdings_snapshots;
drop policy if exists "Public read candles" on crypto_candles;
drop policy if exists "Public read tickers" on crypto_tickers;
drop policy if exists "Public read audit" on crypto_audit_log;
drop policy if exists "Public read plans" on daily_gameplans;
drop policy if exists "Public read items" on daily_gameplan_items;
-- Create PUBLIC READ policies (Dashboard Access)
create policy "Public read orders" on crypto_orders for
select to anon using (true);
create policy "Public read snapshots" on crypto_cash_snapshots for
select to anon using (true);
create policy "Public read holdings" on crypto_holdings_snapshots for
select to anon using (true);
create policy "Public read candles" on crypto_candles for
select to anon using (true);
create policy "Public read tickers" on crypto_tickers for
select to anon using (true);
create policy "Public read audit" on crypto_audit_log for
select to anon using (true);
create policy "Public read plans" on daily_gameplans for
select to anon using (true);
create policy "Public read items" on daily_gameplan_items for
select to anon using (true);
-- Create SERVICE WRITE policies (Bot Access)
create policy "Service write all" on crypto_orders for all to service_role using (true) with check (true);
create policy "Service write snapshots" on crypto_cash_snapshots for all to service_role using (true) with check (true);
create policy "Service write holdings" on crypto_holdings_snapshots for all to service_role using (true) with check (true);
create policy "Service write candles" on crypto_candles for all to service_role using (true) with check (true);
create policy "Service write tickers" on crypto_tickers for all to service_role using (true) with check (true);
create policy "Service write audit" on crypto_audit_log for all to service_role using (true) with check (true);
create policy "Service write plans" on daily_gameplans for all to service_role using (true) with check (true);
create policy "Service write items" on daily_gameplan_items for all to service_role using (true) with check (true);
