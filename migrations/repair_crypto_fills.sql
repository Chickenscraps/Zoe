-- Repair migration for missing crypto_fills table
-- Run this in Supabase SQL Editor to fix dashboard "Fills" view
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
create index if not exists crypto_fills_order_id_executed_at_idx on public.crypto_fills(order_id, executed_at desc);
