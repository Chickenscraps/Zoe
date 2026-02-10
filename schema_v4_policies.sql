-- ZOE V4 PRO - STEP 2: INDEXES & POLICIES
-- Run this SECOND, only after Step 1 has completed without errors.
-- 1. Indexes (depend on columns existing)
create unique index if not exists daily_pnl_account_date_idx on public.daily_pnl(account_id, date);
create unique index if not exists positions_account_symbol_idx on public.positions(account_id, symbol);
-- 2. Enable RLS
alter table public.users enable row level security;
alter table public.accounts enable row level security;
alter table public.trades enable row level security;
alter table public.orders enable row level security;
alter table public.positions enable row level security;
-- 3. Policies (Drop/Create for Idempotency)
DROP POLICY IF EXISTS "allow_public_read_daily_pnl" ON public.daily_pnl;
DROP POLICY IF EXISTS "allow_public_read_trades" ON public.trades;
DROP POLICY IF EXISTS "allow_public_read_positions" ON public.positions;
CREATE POLICY "allow_public_read_daily_pnl" ON public.daily_pnl FOR
SELECT USING (true);
CREATE POLICY "allow_public_read_trades" ON public.trades FOR
SELECT USING (true);
CREATE POLICY "allow_public_read_positions" ON public.positions FOR
SELECT USING (true);
