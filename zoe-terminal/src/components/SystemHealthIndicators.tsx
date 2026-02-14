/**
 * Iron Lung health indicators for the AppShell header.
 *
 * Components:
 * - SyncLagBadge: green/yellow/red dot based on sync lag
 * - TrustIndicator: quote freshness dot
 * - CircuitBreakerBanner: alert bar when breakers are active
 *
 * References: [HL] §Monitoring, [AA] §8.1
 */
import { AlertTriangle, Activity, Wifi } from 'lucide-react';
import { cn } from '../lib/utils';
import type { SystemHealth } from '../hooks/useSystemHealth';

interface HealthIndicatorProps {
  health: SystemHealth;
}

/**
 * Small dot indicator for sync lag health.
 * Green: <5s | Yellow: 5-30s | Red: >30s
 */
export function SyncLagBadge({ health }: HealthIndicatorProps) {
  const lag = health.metrics.syncLagMs;
  const status = lag <= 0
    ? 'unknown'
    : lag < 5000
      ? 'ok'
      : lag < 30000
        ? 'warning'
        : 'error';

  const colors = {
    ok: 'bg-profit',
    warning: 'bg-yellow-400',
    error: 'bg-loss',
    unknown: 'bg-text-muted/30',
  };

  const labels = {
    ok: 'Sync OK',
    warning: `Sync lag ${(lag / 1000).toFixed(0)}s`,
    error: `Sync lag ${(lag / 1000).toFixed(0)}s`,
    unknown: 'No sync data',
  };

  return (
    <div
      className="flex items-center gap-1.5 cursor-default"
      title={labels[status]}
    >
      <Wifi className={cn(
        "w-3 h-3",
        status === 'ok' ? 'text-profit/60' :
        status === 'warning' ? 'text-yellow-400/60' :
        status === 'error' ? 'text-loss/60' :
        'text-text-muted/30'
      )} />
      <span className={cn(
        "w-1.5 h-1.5 rounded-full",
        colors[status],
        status === 'ok' && 'animate-pulse',
      )} />
    </div>
  );
}

/**
 * Small dot indicator for quote freshness.
 * Green: stale rate <5% | Yellow: 5-20% | Red: >20%
 */
export function TrustIndicator({ health }: HealthIndicatorProps) {
  const staleRate = health.metrics.staleQuoteRate;
  const status = staleRate < 5 ? 'ok' : staleRate < 20 ? 'warning' : 'error';

  const colors = {
    ok: 'text-profit/60',
    warning: 'text-yellow-400/60',
    error: 'text-loss/60',
  };

  const labels = {
    ok: 'Quotes fresh',
    warning: `${staleRate.toFixed(0)}% stale quotes`,
    error: `${staleRate.toFixed(0)}% stale quotes`,
  };

  return (
    <div
      className="flex items-center gap-1"
      title={labels[status]}
    >
      <Activity className={cn("w-3 h-3", colors[status])} />
    </div>
  );
}

/**
 * Alert banner when circuit breakers are active.
 * Shows below the mode banner, above the header.
 */
export function CircuitBreakerBanner({ health }: HealthIndicatorProps) {
  if (!health.circuitBreakers.active || health.circuitBreakers.breakers.length === 0) {
    return null;
  }

  const latestBreaker = health.circuitBreakers.breakers[0];
  const severity = latestBreaker.severity === 'critical' ? 'bg-loss/20 text-loss border-loss/30' : 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30';

  return (
    <div className={cn(
      "w-full text-center py-1.5 text-[10px] font-bold tracking-[0.15em] uppercase z-[59] relative select-none border-b flex items-center justify-center gap-2",
      severity,
    )}>
      <AlertTriangle className="w-3 h-3" />
      <span>
        Circuit Breaker: {latestBreaker.name}
        {latestBreaker.message && (
          <span className="font-normal opacity-70 ml-1.5">— {latestBreaker.message.slice(0, 80)}</span>
        )}
      </span>
    </div>
  );
}

/**
 * Compact health cluster for the header — combines sync lag + trust indicators.
 */
export function HealthCluster({ health }: HealthIndicatorProps) {
  if (health.loading) return null;

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-surface-base/50 border border-border">
      <SyncLagBadge health={health} />
      <div className="w-px h-3 bg-border" />
      <TrustIndicator health={health} />
    </div>
  );
}
