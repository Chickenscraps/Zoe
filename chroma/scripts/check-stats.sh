#!/bin/bash
# Check Chroma analytics from Supabase zoe_events table
SUPABASE_URL="https://qwdkadwuyejyadwptgfd.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3ZGthZHd1eWVqeWFkd3B0Z2ZkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDYwMzUzNCwiZXhwIjoyMDg2MTc5NTM0fQ.cCEqVZM8heQ47bP0cW0gfthBT0P41W8sizJpINDQ-9w"

echo "═══════════════════════════════════"
echo "  CHROMA ANALYTICS DASHBOARD"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "═══════════════════════════════════"
echo ""

# Total events
TOTAL=$(curl -s -H "apikey: $SUPABASE_KEY" -H "Authorization: Bearer $SUPABASE_KEY" \
  -H "Prefer: count=exact" \
  "$SUPABASE_URL/rest/v1/zoe_events?source=eq.chroma&select=id" \
  -I 2>&1 | grep -i 'content-range' | grep -oP '\d+$')
echo "Total events: ${TOTAL:-0}"

# Events by type
echo ""
echo "Events by type:"
curl -s -H "apikey: $SUPABASE_KEY" -H "Authorization: Bearer $SUPABASE_KEY" \
  "$SUPABASE_URL/rest/v1/zoe_events?source=eq.chroma&select=subtype&order=created_at.desc" 2>&1 | \
  python3 -c "
import sys, json
from collections import Counter
try:
    data = json.load(sys.stdin)
    counts = Counter(e['subtype'] for e in data)
    for event, count in counts.most_common():
        print(f'  {event}: {count}')
    print(f'  TOTAL: {len(data)}')
except: print('  (no data)')
"

# Unique sessions
echo ""
echo "Unique sessions:"
curl -s -H "apikey: $SUPABASE_KEY" -H "Authorization: Bearer $SUPABASE_KEY" \
  "$SUPABASE_URL/rest/v1/zoe_events?source=eq.chroma&select=metadata&order=created_at.desc" 2>&1 | \
  python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sessions = set()
    referrers = {}
    for e in data:
        m = e.get('metadata', {}) or {}
        sid = m.get('session_id')
        if sid: sessions.add(sid)
        ref = m.get('referrer', 'unknown')
        referrers[ref] = referrers.get(ref, 0) + 1
    print(f'  Unique sessions: {len(sessions)}')
    print(f'  Referrer breakdown:')
    for ref, count in sorted(referrers.items(), key=lambda x: -x[1]):
        print(f'    {ref}: {count}')
except: print('  (no data)')
"

# Top scores
echo ""
echo "Top scores (game_over events):"
curl -s -H "apikey: $SUPABASE_KEY" -H "Authorization: Bearer $SUPABASE_KEY" \
  "$SUPABASE_URL/rest/v1/zoe_events?source=eq.chroma&subtype=eq.game_over&select=metadata,created_at&order=created_at.desc&limit=10" 2>&1 | \
  python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for e in data:
        m = e.get('metadata', {}) or {}
        level = m.get('level', '?')
        score = m.get('score', '?')
        ts = e.get('created_at', '')[:19]
        print(f'  Level {level} | Score {score} | {ts}')
    if not data: print('  (no games completed yet)')
except: print('  (no data)')
"

echo ""
echo "═══════════════════════════════════"
