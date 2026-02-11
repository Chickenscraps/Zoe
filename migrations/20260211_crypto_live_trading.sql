-- Robinhood crypto live-trading schema for reconciliation and safety gates.

create table if not exists public.crypto_orders (
  id uuid primary key default gen_random_uuid(),
  client_order_id text not null unique,
  symbol text not null,
  side text not null check (side in ('buy', 'sell')),
  order_type text not null check (order_type in ('market', 'limit')),
  qty numeric,
  notional numeric,
  status text not null check (status in ('new', 'submitted', 'partially_filled', 'filled', 'canceled', 'rejected')),
  requested_at timestamptz not null default now(),
  submitted_at timestamptz,
  updated_at timestamptz not null default now(),
  raw_response jsonb not null default '{}'::jsonb
);

create table if not exists public.crypto_fills (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.crypto_orders(id) on delete cascade,
  fill_id text not null unique,
  symbol text not null,
  side text not null check (side in ('buy', 'sell')),
  qty numeric not null,
  price numeric not null,
  fee numeric not null default 0,
  executed_at timestamptz not null,
  raw_fill jsonb not null default '{}'::jsonb
);

create table if not exists public.crypto_holdings_snapshots (
  id uuid primary key default gen_random_uuid(),
  taken_at timestamptz not null default now(),
  holdings jsonb not null,
  total_crypto_value numeric not null default 0,
  source text not null default 'robinhood' check (source = 'robinhood')
);

create table if not exists public.crypto_cash_snapshots (
  id uuid primary key default gen_random_uuid(),
  taken_at timestamptz not null default now(),
  cash_available numeric not null default 0,
  buying_power numeric not null default 0,
  source text not null default 'robinhood' check (source = 'robinhood')
);

create table if not exists public.crypto_reconciliation_events (
  id uuid primary key default gen_random_uuid(),
  taken_at timestamptz not null default now(),
  local_cash numeric not null,
  rh_cash numeric not null,
  cash_diff numeric not null,
  local_holdings jsonb not null,
  rh_holdings jsonb not null,
  holdings_diff jsonb not null,
  status text not null check (status in ('ok', 'degraded')),
  reason text
);

create table if not exists public.daily_notional (
  day date primary key,
  notional_used numeric not null default 0
);

create index if not exists crypto_orders_status_requested_at_idx
  on public.crypto_orders(status, requested_at desc);

create index if not exists crypto_fills_order_id_executed_at_idx
  on public.crypto_fills(order_id, executed_at desc);

create index if not exists crypto_holdings_snapshots_taken_at_idx
  on public.crypto_holdings_snapshots(taken_at desc);

create index if not exists crypto_cash_snapshots_taken_at_idx
  on public.crypto_cash_snapshots(taken_at desc);

create index if not exists crypto_reconciliation_events_taken_at_idx
  on public.crypto_reconciliation_events(taken_at desc);
