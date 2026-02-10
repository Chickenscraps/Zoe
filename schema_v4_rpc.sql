-- ZOE V4 PRO - STEP 3: RPC API (Corrected)
-- Run this to create helper functions for the Dashboard (JS Client).
-- 1. Get Account Header (Equity, Cash, Day P&L)
-- Usage: supabase.rpc('get_account_overview', { p_discord_id: '...' })
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
-- 2. Get Open Positions with P&L
-- Usage: supabase.rpc('get_positions_report', { p_account_id: '...' })
create or replace function public.get_positions_report(p_account_id uuid default null) returns table (
        symbol text,
        quantity int,
        avg_price numeric,
        current_price numeric,
        market_value numeric,
        unrealized_pnl numeric,
        pnl_percent numeric
    ) language plpgsql security definer as $$
declare v_acc_id uuid;
begin if p_account_id is null then
select id into v_acc_id
from public.accounts
limit 1;
else v_acc_id := p_account_id;
end if;
return query
select p.symbol,
    p.quantity,
    p.avg_price,
    p.current_price,
    p.market_value,
    (p.market_value - (p.avg_price * p.quantity)) as unrealized_pnl,
    case
        when (p.avg_price * p.quantity) = 0 then 0
        else round(
            (
                (
                    (p.market_value - (p.avg_price * p.quantity)) / (p.avg_price * p.quantity)
                ) * 100
            ),
            2
        )
    end as pnl_percent
from public.positions p
where p.account_id = v_acc_id
    and p.quantity != 0
order by p.market_value desc;
end;
$$;
-- 3. Get Activity Feed
-- Usage: supabase.rpc('get_activity_feed', { p_limit: 10 })
create or replace function public.get_activity_feed(p_limit int default 10) returns table (
        type text,
        symbol text,
        details text,
        event_ts timestamptz
    ) language plpgsql security definer as $$ begin return query (
        select 'TRADE' as type,
            symbol,
            (
                side || ' ' || quantity::text || ' @ $' || price::text
            ) as details,
            timestamp as event_ts
        from public.fills
        order by timestamp desc
        limit p_limit
    )
union all
(
    select 'SYSTEM' as type,
        'ZOE' as symbol,
        action as details,
        timestamp as event_ts
    from public.audit_log
    order by timestamp desc
    limit p_limit
)
order by event_ts desc
limit p_limit;
end;
$$;
