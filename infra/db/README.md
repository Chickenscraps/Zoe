# Zoe V4 Database Migrations

## Setup

Run migrations in order against your Supabase SQL Editor:

```
migrations/001_v4_base_tables.sql
```

All migrations are idempotent (`CREATE TABLE IF NOT EXISTS`, `DROP POLICY IF EXISTS`).

## Schema Overview

| Table | Purpose |
|---|---|
| `users` | Discord user identity |
| `accounts` | Paper trading account state ($2k starting) |
| `trades` | Trade lifecycle (open/close, strategy, P&L) |
| `orders` | Order records with legs |
| `fills` | Execution fills with slippage |
| `positions` | Open positions with mark-to-market |
| `daily_pnl` | Daily performance snapshots |
| `pnl_timeseries` | Intraday equity curve points |
| `option_chain_snapshots` | Polygon option chain captures |
| `research_items` | Trends/X/Bloomberg research data |
| `features_daily` | Per-symbol daily feature vectors |
| `strategy_registry` | Strategy catalog with versioning |
| `experiment_runs` | Backtest/walk-forward results |
| `health_reports` | Self-heal diagnostic reports |
| `daily_gameplans` | Pre-market trading plans |
| `audit_log` | System activity log |
| `config` | Runtime config key/value store |
