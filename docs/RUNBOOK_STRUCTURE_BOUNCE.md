# Runbook: Trendlines + Key Levels & Bounce Catcher

## Quick Reference

| Module | Package | Config Key | Default State |
|--------|---------|------------|---------------|
| Trendlines & Levels | `trendlines/` | `trendlines:` | **enabled** |
| Bounce Catcher | `bounce/` | `bounce:` | **shadow (disabled)** |
| Integration Layer | `services/structure_context.py` | — | active |

---

## 1. File Tree (New Files)

```
trendlines/
├── __init__.py           # Public exports
├── config.py             # TrendlinesConfig dataclass
├── pivots.py             # Vectorized fractal pivot detection
├── ransac_fit.py         # Sequential RANSAC trendline fitting
├── dbscan_levels.py      # DBSCAN horizontal level clustering
├── scoring.py            # 0-100 scoring engine + confluence
├── events.py             # Breakout / breakdown / retest detection
├── persistence.py        # Supabase read/write layer
├── api.py                # StructureAPI facade (consumed by strategies)
└── tests/
    ├── fixtures.py       # Deterministic OHLCV generators
    ├── test_pivots.py
    ├── test_ransac.py
    ├── test_dbscan.py
    ├── test_scoring.py
    └── test_events.py

bounce/
├── __init__.py
├── config.py             # BounceConfig dataclass
├── capitulation.py       # Phase 1: waterfall detection
├── stabilization.py      # Phase 2: 2-of-4 confirmation
├── bounce_score.py       # 0-100 scoring
├── entry_planner.py      # TradeIntent builder
├── exit_planner.py       # TP/SL/time/panic exits
├── guards.py             # Hard halt conditions
├── bounce_catcher.py     # 3-phase state machine orchestrator
└── tests/
    ├── fixtures.py       # Capitulation / falling-knife generators
    ├── test_detectors.py # Unit tests (wick ratio, cap, stab, score)
    └── test_integration.py # State machine transitions, guards, exits

services/
└── structure_context.py  # Integration: trendlines ↔ bounce ↔ strategies

migrations/
└── 20260211_trendlines_and_bounce.sql  # All new tables + indexes

tests/
└── test_structure_bounce_integration.py  # Cross-module fusion tests

config.yaml               # Extended with trendlines: and bounce: sections
```

---

## 2. Running Tests

```bash
# All tests (66 total)
python -m pytest trendlines/tests/ bounce/tests/ tests/test_structure_bounce_integration.py -v

# Just trendlines (34 tests)
python -m pytest trendlines/tests/ -v

# Just bounce (30 tests)
python -m pytest bounce/tests/ -v

# Just cross-module integration (2 tests)
python -m pytest tests/test_structure_bounce_integration.py -v
```

**Expected**: 66 passed, 0 failed.

---

## 3. Database Migration

Run the migration in your Supabase SQL editor:

```bash
# Copy-paste the contents of:
migrations/20260211_trendlines_and_bounce.sql
```

This creates 6 tables:
- `market_pivots` — atomic structural events
- `technical_trendlines` — RANSAC output
- `technical_levels` — DBSCAN output
- `structure_events` — breakout/breakdown/retest log
- `bounce_events` — state machine audit trail
- `bounce_intents` — trade intents (emitted or blocked)

---

## 4. Configuration

All config lives in `config.yaml` under `trendlines:` and `bounce:` sections.

### Key Operational Toggles

| Toggle | YAML Path | Default | Effect |
|--------|-----------|---------|--------|
| Trendlines on/off | `trendlines.enabled` | `true` | Disable all pivot/RANSAC/DBSCAN |
| Bounce shadow mode | `bounce.enabled` | `false` | Detect+log but never emit trade intent |
| Bounce live | `bounce.enabled` | `true` | Emit TradeIntents to executor |
| Universe | `*.universe` | `[BTC-USD, ETH-USD]` | Which symbols to analyze |
| Min bounce score | `bounce.scoring.min_score` | `70` | Score threshold for intent emission |
| Vol halt | `bounce.vol_halt_24h_range` | `0.05` | Block entries if 24h range > 5% |
| Spread halt | `bounce.execution.max_spread_pct_to_trade` | `0.003` | Block if spread > 0.3% |
| Weekend dampener | `bounce.weekend_dampener` | `false` | Reduce entries on weekends |
| Alert throttle | `bounce.alerts.throttle_minutes` | `30` | Max 1 Discord alert per 30m/symbol |

---

## 5. Debug Playbook

### Inspect Pivots
```sql
-- Latest pivots for BTC-USD 15m
SELECT * FROM market_pivots
WHERE symbol = 'BTC-USD' AND timeframe = '15m'
ORDER BY timestamp DESC LIMIT 50;

-- Count by source type
SELECT source, type, count(*) FROM market_pivots
WHERE symbol = 'BTC-USD' AND timeframe = '15m'
GROUP BY source, type;
```

### Inspect Trendlines & Levels
```sql
-- Active trendlines
SELECT id, side, slope, intercept, inlier_count, score, start_at, end_at
FROM technical_trendlines
WHERE symbol = 'BTC-USD' AND timeframe = '1h' AND is_active = true
ORDER BY score DESC;

-- Active levels
SELECT id, role, price_centroid, price_top, price_bottom, touch_count, score
FROM technical_levels
WHERE symbol = 'BTC-USD' AND timeframe = '1h' AND is_active = true
ORDER BY score DESC;
```

### Inspect Bounce States
```sql
-- Recent bounce events
SELECT ts, symbol, prev_state, state, score, reason_json
FROM bounce_events
WHERE symbol = 'BTC-USD'
ORDER BY ts DESC LIMIT 20;

-- Bounce intents (emitted + blocked)
SELECT ts, symbol, entry_style, entry_price, score, blocked, blocked_reason
FROM bounce_intents
WHERE symbol = 'BTC-USD'
ORDER BY ts DESC LIMIT 20;
```

### Reproduce a Signal Deterministically
```python
import pandas as pd
from trendlines.api import StructureAPI
from trendlines.config import TrendlinesConfig
from bounce.capitulation import detect_capitulation_event

# Load exact same candles from your data source
df = pd.DataFrame(your_candle_data)  # must match the production data

# Trendlines are deterministic (random_state=42)
api = StructureAPI(TrendlinesConfig())
result = api.update("BTC-USD", "15m", df)
print(result["trendlines"])
print(result["levels"])

# Capitulation is deterministic (pure math, no randomness)
is_cap, metrics = detect_capitulation_event(df)
print(is_cap, metrics)
```

---

## 6. Safe Activation Steps

### Phase 1: Deploy in Shadow Mode (48h)

1. Merge the code
2. Run migration SQL in Supabase
3. Config should already have `bounce.enabled: false`
4. Deploy — trendlines module runs live, bounce detects but doesn't trade
5. Monitor for 48 hours:

```sql
-- Check bounce detection rate
SELECT date_trunc('hour', ts) as hr, count(*),
       count(*) FILTER (WHERE state = 'CAPITULATION_DETECTED') as caps,
       count(*) FILTER (WHERE state = 'STABILIZATION_CONFIRMED') as stabs
FROM bounce_events
WHERE ts > now() - interval '48 hours'
GROUP BY hr ORDER BY hr;

-- Check false positive rate (intents that would have been blocked)
SELECT count(*) FILTER (WHERE blocked = true) as blocked,
       count(*) FILTER (WHERE blocked = false) as would_emit,
       avg(score) as avg_score
FROM bounce_intents
WHERE ts > now() - interval '48 hours';
```

### Phase 2: Evaluate Acceptance Criteria

Before enabling live:
- [ ] Trendlines appear stable (no jitter between updates)
- [ ] Levels cluster near visually obvious S/R zones on chart
- [ ] Bounce detections are rare (< 5/day for BTC-USD is normal)
- [ ] No false capitulations on normal candles
- [ ] Shadow intents have reasonable scores (70+ are rare and high quality)
- [ ] Falling-knife scenarios correctly stayed in cash
- [ ] All 66 tests pass
- [ ] Discord alerts are throttled and readable (not spam)

### Phase 3: Enable Live Intent Emission

1. Update `config.yaml`:
   ```yaml
   bounce:
     enabled: true
   ```
2. The executor must be ready to consume `TradeIntent` objects
3. Monitor first 3 live bounce trades carefully
4. If unexpected behavior, set `enabled: false` immediately

### Emergency: Immediate Halt

```yaml
# In config.yaml:
bounce:
  enabled: false
```

Or via admin Discord command (if wired):
```
/bounce_pause
```

The bot will continue detecting and logging but won't emit any trade intents.

---

## 7. Architecture Notes

### Data Flow
```
Candle Close Event
    ↓
StructureContextService.on_candle_close()
    ↓
┌─────────────────────────┐
│ StructureAPI.update()   │  ← trendlines package
│   pivots → RANSAC       │
│   pivots → DBSCAN       │
│   score → persist       │
└─────────┬───────────────┘
          ↓
┌─────────────────────────┐
│ BounceCatcher            │  ← bounce package
│   .process_tick()       │
│   Phase 1: capitulation │
│   Phase 2: stabilization│
│   Phase 3: score + emit │
│   Guards: halt checks   │
└─────────┬───────────────┘
          ↓
TradeIntent → Execution Engine (existing)
```

### Determinism Guarantees
- RANSAC: `random_state=42` → same pivots = same lines
- DBSCAN: fully deterministic (no randomness)
- Capitulation: pure arithmetic (ATR, volume, wick ratio)
- Scoring: deterministic weighted sum
- State machine: persisted transitions, restart-recoverable

### Safety Layers
1. **Shadow mode** (bounce.enabled=false): detect only
2. **Guards**: spread, volatility, event risk, weekend
3. **Score threshold**: min_score=70 by default
4. **3-phase state machine**: no falling-knife entries
5. **Existing execution gates**: sizing, churn, notional limits
6. **Admin controls**: pause/resume via Discord
