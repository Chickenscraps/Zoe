-- ZOE V4 DASHBOARD QUERIES
-- Use these queries in your Supabase JS Client (or similar) to build the UI.
-- 1. ACCOUNT HEADER (Equity, Cash, Buying Power)
-- Replace 'YOUR_USER_ID' with the logged-in user's UUID (or fetch by discord_id)
select equity,
    cash,
    buying_power,
    pdt_count
from public.accounts
where instance_id = 'default'
order by updated_at desc
limit 1;
-- 2. OPEN POSITIONS WIDGET
select symbol,
    quantity,
    avg_price,
    current_price,
    market_value,
    (market_value - (avg_price * quantity)) as unrealized_pnl
from public.positions
where quantity != 0;
-- 3. RECENT TRADES WIDGET
select symbol,
    side,
    quantity,
    price,
    timestamp
from public.fills
order by timestamp desc
limit 10;
-- 4. EQUITY CURVE (Chart)
select date,
    end_equity
from public.daily_pnl
order by date asc;
-- 5. CLOSED TRADE HISTORY (Log)
select symbol,
    strategy,
    entry_price,
    exit_price,
    pnl,
    notes
from public.trades
where status = 'closed'
order by exit_time desc
limit 20;
-- 6. AUDIT LOG (System Health)
select action,
    details,
    timestamp
from public.audit_log
order by timestamp desc
limit 50;
