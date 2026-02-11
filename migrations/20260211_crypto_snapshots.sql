-- 20260211_crypto_snapshots.sql
-- Missing tables for Cash and Holdings Snapshots
-- 1. Cash Snapshots
create table if not exists crypto_cash_snapshots (
    id uuid primary key default uuid_generate_v4(),
    cash_available numeric not null,
    buying_power numeric not null,
    taken_at timestamptz default now()
);
-- 2. Holdings Snapshots
create table if not exists crypto_holdings_snapshots (
    id uuid primary key default uuid_generate_v4(),
    holdings jsonb not null,
    -- Stores {"BTC-USD": 0.5, "ETH-USD": 2.0}
    total_value numeric not null default 0,
    taken_at timestamptz default now()
);
-- 3. Reconciliation Events (Heartbeat)
create table if not exists crypto_reconciliation_events (
    id uuid primary key default uuid_generate_v4(),
    status text not null,
    -- 'ok', 'degraded', 'error'
    reason text,
    taken_at timestamptz default now()
);
-- 4. Daily Notional Tracker
create table if not exists daily_notional (
    day date primary key default current_date,
    notional_used numeric default 0,
    last_updated timestamptz default now()
);
-- RLS Policies
alter table crypto_cash_snapshots enable row level security;
alter table crypto_holdings_snapshots enable row level security;
alter table crypto_reconciliation_events enable row level security;
alter table daily_notional enable row level security;
-- Public Read (Dashboard)
create policy "Public read snapshots" on crypto_cash_snapshots for
select to anon using (true);
create policy "Public read holdings" on crypto_holdings_snapshots for
select to anon using (true);
create policy "Public read reconciliation" on crypto_reconciliation_events for
select to anon using (true);
create policy "Public read daily_notional" on daily_notional for
select to anon using (true);
-- Service Role Write (Bot)
create policy "Service write snapshots" on crypto_cash_snapshots for all to service_role using (true) with check (true);
create policy "Service write holdings" on crypto_holdings_snapshots for all to service_role using (true) with check (true);
create policy "Service write reconciliation" on crypto_reconciliation_events for all to service_role using (true) with check (true);
create policy "Service write daily_notional" on daily_notional for all to service_role using (true) with check (true);
