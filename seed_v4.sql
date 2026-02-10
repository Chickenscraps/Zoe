-- ZOE V4 SEED DATA
-- Run this to populate the DB with initial data for Dashboard testing.
-- 1. Create/Ensure User (Josh / Chickenscraps)
insert into public.users (discord_id, username)
values ('292890243852664855', 'Chickenscraps') on conflict (discord_id) do nothing;
-- 2. Create/Ensure Account
-- We need the user_id to link, so we select it.
do $$
declare v_user_id uuid;
v_account_id uuid;
begin
select id into v_user_id
from public.users
where discord_id = '292890243852664855';
if v_user_id is not null then
insert into public.accounts (user_id, instance_id, equity, cash, buying_power)
values (v_user_id, 'default', 2000.00, 2000.00, 2000.00) on conflict do nothing -- (No unique constraint on user_id yet, but usually 1:1)
returning id into v_account_id;
-- If we didn't insert (already exists), find it
if v_account_id is null then
select id into v_account_id
from public.accounts
where user_id = v_user_id
limit 1;
end if;
-- 3. Create Sample Trade (Winner)
if v_account_id is not null then
insert into public.trades (
        account_id,
        symbol,
        strategy,
        status,
        entry_price,
        exit_price,
        quantity,
        pnl,
        notes
    )
values (
        v_account_id,
        'SPY',
        'Lotto Call',
        'closed',
        500.00,
        505.00,
        1,
        5.00,
        'Seed data verification trade'
    );
-- 4. Create Sample Position (Open)
insert into public.positions (
        account_id,
        symbol,
        quantity,
        avg_price,
        current_price,
        market_value
    )
values (v_account_id, 'QQQ', 10, 400.00, 402.00, 4020.00) on conflict (account_id, symbol) do
update
set quantity = 10,
    market_value = 4020.00;
end if;
end if;
end $$;
