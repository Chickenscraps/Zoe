-- 20260211_crypto_tickers.sql
create table if not exists crypto_tickers (
    symbol text primary key,
    price numeric not null,
    change_24h numeric,
    -- Optional, if we can calc it
    last_updated timestamptz default now()
);
-- Enable RLS
alter table crypto_tickers enable row level security;
-- Drop existing policies to avoid conflicts
drop policy if exists "Public tickers are viewable by everyone" on crypto_tickers;
drop policy if exists "Service role has full access" on crypto_tickers;
drop policy if exists "Authenticated users can view tickers" on crypto_tickers;
-- Policy: Allow anonymous read access (Dashboard)
create policy "Public tickers are viewable by everyone" on crypto_tickers for
select to anon using (true);
-- Policy: Allow service role full access (Bot)
create policy "Service role has full access" on crypto_tickers to service_role using (true) with check (true);
-- Also allow authenticated users (if you log in later)
create policy "Authenticated users can view tickers" on crypto_tickers for
select to authenticated using (true);
-- Grants
revoke all on crypto_tickers
from public;
grant select on crypto_tickers to anon;
grant all on crypto_tickers to service_role;
grant select on crypto_tickers to authenticated;
