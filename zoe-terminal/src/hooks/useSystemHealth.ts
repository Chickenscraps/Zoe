/**
 * System health hook — polls zoe_events for Iron Lung metrics.
 *
 * Fetches FILL_QUALITY, METRIC, and CIRCUIT_BREAKER events for:
 * - Sync lag indicator (green/yellow/red)
 * - Fill quality (rolling avg IS bps)
 * - Circuit breaker status
 * - Trust indicator (stale quote rate)
 *
 * References: [HL] §Monitoring, [AA] §8.1
 */
import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../lib/supabaseClient';
import { useModeContext } from '../lib/mode';

export interface FillQualityData {
  avgIsBps: number;
  directionalIsBps: number;
  fillCount: number;
  recentFills: Array<{
    symbol: string;
    side: string;
    isBps: number;
    decisionPrice: number;
    fillPrice: number;
    createdAt: string;
  }>;
}

export interface MetricsSnapshot {
  staleQuoteRate: number;
  spreadBlowoutRate: number;
  syncLagMs: number;
  rejectionRate: number;
  fillRate: number;
  loopJitterP99Ms: number;
  totalTicks: number;
}

export interface CircuitBreakerStatus {
  active: boolean;
  breakers: Array<{
    name: string;
    severity: string;
    message: string;
    triggeredAt: string;
  }>;
}

export interface SystemHealth {
  fillQuality: FillQualityData;
  metrics: MetricsSnapshot;
  circuitBreakers: CircuitBreakerStatus;
  loading: boolean;
  lastUpdated: string | null;
}

const DEFAULT_FILL_QUALITY: FillQualityData = {
  avgIsBps: 0,
  directionalIsBps: 0,
  fillCount: 0,
  recentFills: [],
};

const DEFAULT_METRICS: MetricsSnapshot = {
  staleQuoteRate: 0,
  spreadBlowoutRate: 0,
  syncLagMs: 0,
  rejectionRate: 0,
  fillRate: 0,
  loopJitterP99Ms: 0,
  totalTicks: 0,
};

const DEFAULT_CB: CircuitBreakerStatus = {
  active: false,
  breakers: [],
};

export function useSystemHealth(): SystemHealth {
  const { mode } = useModeContext();
  const [fillQuality, setFillQuality] = useState<FillQualityData>(DEFAULT_FILL_QUALITY);
  const [metrics, setMetrics] = useState<MetricsSnapshot>(DEFAULT_METRICS);
  const [circuitBreakers, setCircuitBreakers] = useState<CircuitBreakerStatus>(DEFAULT_CB);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      // Fetch FILL_QUALITY events (last 50)
      const { data: fillEvents } = await supabase
        .from('zoe_events')
        .select('id, created_at, meta_json, body')
        .eq('type', 'FILL_QUALITY')
        .eq('mode', mode)
        .order('created_at', { ascending: false })
        .limit(50);

      if (fillEvents && fillEvents.length > 0) {
        const fills = fillEvents.map((e: any) => {
          const meta = typeof e.meta_json === 'string' ? JSON.parse(e.meta_json) : (e.meta_json || {});
          return {
            symbol: meta.symbol || '',
            side: meta.side || '',
            isBps: meta.is_bps ?? 0,
            decisionPrice: meta.decision_price ?? 0,
            fillPrice: meta.fill_price ?? 0,
            createdAt: e.created_at,
          };
        });

        const totalIs = fills.reduce((sum: number, f: any) => sum + Math.abs(f.isBps), 0);
        const directionalIs = fills.reduce((sum: number, f: any) => sum + f.isBps, 0);

        setFillQuality({
          avgIsBps: fills.length > 0 ? totalIs / fills.length : 0,
          directionalIsBps: fills.length > 0 ? directionalIs / fills.length : 0,
          fillCount: fills.length,
          recentFills: fills.slice(0, 20),
        });
      } else {
        setFillQuality(DEFAULT_FILL_QUALITY);
      }

      // Fetch latest METRIC event
      const { data: metricEvents } = await supabase
        .from('zoe_events')
        .select('id, created_at, meta_json')
        .eq('type', 'METRIC')
        .eq('mode', mode)
        .order('created_at', { ascending: false })
        .limit(1);

      if (metricEvents && metricEvents.length > 0) {
        const meta = typeof metricEvents[0].meta_json === 'string'
          ? JSON.parse(metricEvents[0].meta_json)
          : (metricEvents[0].meta_json || {});

        setMetrics({
          staleQuoteRate: meta.stale_quote_rate ?? 0,
          spreadBlowoutRate: meta.spread_blowout_rate ?? 0,
          syncLagMs: meta.sync_lag_ms ?? 0,
          rejectionRate: meta.rejection_rate ?? 0,
          fillRate: meta.fill_rate ?? 0,
          loopJitterP99Ms: meta.loop_jitter_p99_ms ?? 0,
          totalTicks: meta.total_ticks ?? 0,
        });
      } else {
        setMetrics(DEFAULT_METRICS);
      }

      // Fetch active CIRCUIT_BREAKER events (last hour)
      const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();
      const { data: cbEvents } = await supabase
        .from('zoe_events')
        .select('id, created_at, meta_json, body')
        .eq('type', 'CIRCUIT_BREAKER')
        .eq('mode', mode)
        .gte('created_at', oneHourAgo)
        .order('created_at', { ascending: false })
        .limit(10);

      if (cbEvents && cbEvents.length > 0) {
        const breakers = cbEvents.map((e: any) => {
          const meta = typeof e.meta_json === 'string' ? JSON.parse(e.meta_json) : (e.meta_json || {});
          return {
            name: meta.breaker_name || meta.name || 'Unknown',
            severity: meta.severity || 'warning',
            message: e.body || '',
            triggeredAt: e.created_at,
          };
        });

        setCircuitBreakers({
          active: breakers.length > 0,
          breakers,
        });
      } else {
        setCircuitBreakers(DEFAULT_CB);
      }

      setLastUpdated(new Date().toISOString());
    } catch (err) {
      console.warn('System health fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30_000); // Poll every 30s
    return () => clearInterval(interval);
  }, [fetchHealth]);

  return { fillQuality, metrics, circuitBreakers, loading, lastUpdated };
}
