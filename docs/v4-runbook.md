# Zoe V4 Runbook

## Quick Start

```bash
# 1. Install dependencies
pnpm install

# 2. Configure environment
cp services/.env.example services/.env
# Edit services/.env with your API keys

# 3. Run Supabase migration
# Paste infra/db/migrations/001_v4_base_tables.sql into Supabase SQL Editor

# 4. Build all V4 services
pnpm v4:build

# 5. Run tests
pnpm v4:test

# 6. Start the trader (paper mode)
pnpm v4:start
```

## Environment Variables

See `services/.env.example` for all required/optional variables.

**Required for core trading**:
- `SUPABASE_URL` + `SUPABASE_KEY`
- `POLYGON_API_KEY`

**Required for Discord**:
- `DISCORD_TOKEN` + `DISCORD_CHANNEL_ID`

## Common Operations

### Check account status
```bash
# Via Discord
/positions
/pnl today

# Via dashboard
open http://localhost:3000
```

### Manual trade (paper)
```bash
# Via Discord
/explain <trade_id>
```

### Health check
```bash
pnpm v4:health
```

### Reset paper account
```sql
-- In Supabase SQL Editor
UPDATE public.accounts
SET equity = 2000, cash = 2000, buying_power = 2000, pdt_count = 0
WHERE instance_id = 'default';
```

## Troubleshooting

### Polygon API errors
- Check `POLYGON_API_KEY` is set and valid
- Free tier has rate limits (5 req/min). Consider Basic plan for options data.

### PDT violations
- Check `accounts.day_trades_history` for the rolling 5-day window
- Wait for oldest day trade to fall off the window

### Supabase connection issues
- Verify `SUPABASE_URL` and `SUPABASE_KEY`
- Check RLS policies allow reads
- For writes, use `SUPABASE_SERVICE_ROLE_KEY`

## Milestones

- [x] M0: Project structure, configs, env templates
- [ ] M1: Supabase schema completion + migration tooling
- [ ] M2: Market data service (Polygon + caching)
- [ ] M3: Paper broker (PDT + slippage)
- [ ] M4: Trader loop (session-aware)
- [ ] M5: Research ingestion
- [ ] M6: Strategy lab
- [ ] M7: Dashboard UI
- [ ] M8: Discord integration
- [ ] M9: Self-heal + health reports
