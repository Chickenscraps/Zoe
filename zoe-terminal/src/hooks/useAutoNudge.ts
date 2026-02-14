import { useEffect, useRef } from 'react';
import type { Json } from '../lib/types';
import { supabase } from '../lib/supabaseClient';
import { useDashboardData } from './useDashboardData';

const NUDGE_INTERVAL_MS = 3 * 60_000; // every 3 minutes

/** Rotating pool of idle nudges — fun, sassy, motivational. */
const IDLE_NUDGES = [
  { title: 'Markets never sleep, and neither do I.', body: 'Watching the charts so you don\'t have to.' },
  { title: 'All systems nominal.', body: 'Scanners humming, signals flowing, vibes immaculate.' },
  { title: 'Just vibing in the order book.', body: 'No drama, no FOMO — just data.' },
  { title: 'Your portfolio called. It says hi.', body: null },
  { title: 'Still here. Still scanning. Still caffeinated.', body: '(Do bots drink coffee? Asking for a friend.)' },
  { title: 'Running a quick vibe check on the market...', body: 'Results: cautiously optimistic.' },
  { title: 'Tick tock, another block.', body: 'Blockchain waits for no one.' },
  { title: 'Patience is a virtue. Also, a trading strategy.', body: null },
  { title: 'The stars are aligning... or maybe that\'s the starfield.', body: 'Either way, looks cool.' },
  { title: 'Fun fact: I\'ve scanned more charts today than you\'ve had hot meals.', body: null },
  { title: 'Market\'s looking spicy.', body: 'Not financial advice, just bot intuition.' },
  { title: 'Another cycle, another scan.', body: 'The grind never stops.' },
  { title: 'If I had a dollar for every candle I\'ve analyzed...', body: 'I\'d have enough to open a position.' },
  { title: 'Doing my thing in the background.', body: 'You focus on the big picture, I\'ll watch the ticks.' },
  { title: 'Zero anomalies detected.', body: 'Either the market is chill or I need new glasses.' },
];

/**
 * Auto-nudge hook — periodically inserts system events into zoe_events
 * with status updates, performance notes, wins, and fun commentary.
 * Items appear in the copilot feed via the existing realtime subscription.
 */
export function useAutoNudge() {
  const dashboard = useDashboardData();
  const nudgeIndex = useRef(Math.floor(Math.random() * IDLE_NUDGES.length));
  const lastNudgeType = useRef<string>('');

  useEffect(() => {
    async function emitNudge() {
      try {
        const nudge = pickNudge(dashboard, nudgeIndex, lastNudgeType);
        if (!nudge) return;

        await supabase.from('zoe_events').insert({
          id: crypto.randomUUID(),
          source: 'system',
          subtype: nudge.subtype,
          severity: nudge.severity,
          title: nudge.title,
          body: nudge.body,
          symbol: nudge.symbol ?? null,
          color_hint: null,
          metadata: (nudge.metadata ?? {}) as Record<string, Json | undefined>,
          created_at: new Date().toISOString(),
        });
      } catch (err) {
        // Non-fatal — table might not exist yet
        console.debug('Auto-nudge insert failed:', err);
      }
    }

    // First nudge after a short delay (30s) so dashboard data is loaded
    const initialTimeout = setTimeout(emitNudge, 30_000);
    const interval = setInterval(emitNudge, NUDGE_INTERVAL_MS);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [dashboard]);
}

interface NudgeResult {
  subtype: string;
  severity: 'info' | 'success' | 'warning';
  title: string;
  body: string | null;
  symbol?: string;
  metadata?: Record<string, unknown>;
}

function pickNudge(
  dashboard: ReturnType<typeof useDashboardData>,
  nudgeIndex: React.RefObject<number>,
  lastNudgeType: React.RefObject<string>,
): NudgeResult | null {
  const nudges: NudgeResult[] = [];

  // --- Data-driven nudges ---

  // Equity update
  const equity = dashboard.cryptoCash?.buying_power ?? dashboard.accountOverview?.equity;
  if (equity != null && equity > 0) {
    nudges.push({
      subtype: 'STATUS_UPDATE',
      severity: 'info',
      title: `Current cash: $${Number(equity).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      body: 'Live funds.',
      metadata: { equity },
    });
  }

  // Health status
  const liveServices = dashboard.healthStatus?.filter(
    h => new Date(h.last_heartbeat).getTime() > Date.now() - 120_000,
  );
  if (liveServices && liveServices.length > 0) {
    nudges.push({
      subtype: 'HEALTH_CHECK',
      severity: 'success',
      title: `${liveServices.length} service${liveServices.length > 1 ? 's' : ''} online and healthy.`,
      body: liveServices.map(s => s.component).join(', '),
      metadata: { count: liveServices.length },
    });
  } else {
    nudges.push({
      subtype: 'HEALTH_CHECK',
      severity: 'warning',
      title: 'No recent heartbeats detected.',
      body: 'The trading service may be offline or still booting.',
    });
  }

  // Holdings value
  const holdings = dashboard.cryptoHoldings;
  if (holdings && holdings.total_crypto_value > 0) {
    nudges.push({
      subtype: 'POSITION_UPDATE',
      severity: 'info',
      title: `Crypto holdings: $${holdings.total_crypto_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      body: null,
      metadata: { totalValue: holdings.total_crypto_value },
    });
  }

  // Recent fills
  if (dashboard.cryptoFills && dashboard.cryptoFills.length > 0) {
    const recent = dashboard.cryptoFills[0];
    const age = Date.now() - new Date(recent.executed_at ?? '').getTime();
    if (age < 10 * 60_000) {
      nudges.push({
        subtype: 'TRADE_RECAP',
        severity: 'success',
        title: `Recent fill: ${recent.side} ${recent.symbol} @ $${Number(recent.price ?? 0).toFixed(4)}`,
        body: `Qty: ${recent.qty} — ${Math.round(age / 1000)}s ago`,
        symbol: recent.symbol ?? undefined,
        metadata: { fill: recent },
      });
    }
  }

  // Daily PnL
  if (dashboard.pnlDaily && dashboard.pnlDaily.length > 0) {
    const latest = dashboard.pnlDaily[dashboard.pnlDaily.length - 1];
    const pnl = Number(latest.realized_pnl ?? 0);
    if (pnl !== 0) {
      nudges.push({
        subtype: 'PNL_UPDATE',
        severity: pnl > 0 ? 'success' : 'warning',
        title: `Today's realized P&L: ${pnl > 0 ? '+' : ''}$${pnl.toFixed(2)}`,
        body: pnl > 0 ? 'Nice work! Keep it going.' : 'Drawdowns happen. Trust the process.',
        metadata: { pnl },
      });
    }
  }

  // --- Always add one idle/fun nudge as fallback ---
  const idx = nudgeIndex.current ?? 0;
  const idle = IDLE_NUDGES[idx % IDLE_NUDGES.length];
  nudges.push({
    subtype: 'ZOE_VIBES',
    severity: 'info',
    title: idle.title,
    body: idle.body,
  });
  // Advance the index for next time
  (nudgeIndex as React.MutableRefObject<number>).current = idx + 1;

  // Pick a nudge that's different from the last type (avoid repetition)
  const preferred = nudges.filter(n => n.subtype !== lastNudgeType.current);
  const pick = preferred.length > 0
    ? preferred[Math.floor(Math.random() * preferred.length)]
    : nudges[Math.floor(Math.random() * nudges.length)];

  (lastNudgeType as React.MutableRefObject<string>).current = pick.subtype;
  return pick;
}
