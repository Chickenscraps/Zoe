# Zoe V4 Architecture

## Overview

Zoe V4 is a paper options trading system built as TypeScript services within the openclaw monorepo. It simulates realistic execution against live Polygon market data with strict PDT enforcement and pessimistic fill modeling.

## Module Map

```
services/
  shared/          @zoe/shared      Types, config validation, market session, logger
  market-data/     @zoe/market-data  Polygon REST/WS, caching, normalization
  paper-broker/    @zoe/paper-broker Execution sim, PDT limiter, slippage model
  broker-mapping/  @zoe/broker-mapping Robinhood symbol resolution
  research/        @zoe/research     Google Trends, X, Bloomberg ingestion
  strategy-lab/    @zoe/strategy-lab Backtests, walk-forward, experiment gates
  trader/          @zoe/trader       Production paper trading loop

apps/
  discord-bot/     @zoe/discord-bot  Announcements, commands, trade cards

infra/
  db/              Database schema & migrations (Supabase/Postgres)
  jobs/            @zoe/jobs         Cron scheduling (market-hours vs off-hours)

dashboard/         Next.js trading dashboard (Tailwind, dark mode)
```

## Data Flow

```
Polygon API  ─→  market-data  ─→  trader  ─→  paper-broker  ─→  Supabase
                      │               │              │
                      │               ▼              ▼
                      │         strategy-lab     fills/positions
                      │               │              │
                      ▼               ▼              ▼
              option_chain_snapshots  experiment_runs  daily_pnl
                                                       │
                                                       ▼
                                              dashboard + discord-bot
```

## Key Constraints

1. **Paper Only**: No real order execution. Ever.
2. **PDT Rule**: Max 3 day trades per rolling 5 trading days.
3. **Pessimistic Fills**: Default crosses the spread + slippage.
4. **$2,000 Account**: Starting simulated equity.
5. **Observability**: Every decision logged with inputs for reproducibility.

## Market Session Behavior

| Session | Zoe's Activity |
|---|---|
| Off-hours (8PM-4AM ET) | Research, self-heal, experiments, plan generation |
| Pre-market (4AM-9:30AM) | 15/10/5 min briefings, watchlist, proposed plays |
| Market open (9:30AM-4PM) | Scan, shortlist, decision, paper execution |
| After-hours (4PM-8PM) | Position review, daily P&L snapshot |

## Tech Stack

- **Runtime**: Node.js 22+ / TypeScript 5.9+
- **Monorepo**: pnpm workspaces
- **Database**: Supabase (PostgreSQL + RLS)
- **Market Data**: Polygon.io REST + WebSocket
- **Frontend**: Next.js 16 + Tailwind 4
- **Testing**: Vitest
- **Config**: Zod validation
