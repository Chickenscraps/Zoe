import { useMemo } from 'react';
import { AlertTriangle, Radio, XCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import { useDashboardData } from '../hooks/useDashboardData';

interface Alert {
  id: string;
  severity: 'warning' | 'critical';
  icon: React.ReactNode;
  message: string;
}

export function AlertBanner() {
  const { cryptoOrders, healthSummary } = useDashboardData();

  const alerts = useMemo<Alert[]>(() => {
    const result: Alert[] = [];

    // Stuck orders: age > 5min and replace_count >= 3
    const stuckCount = (cryptoOrders ?? []).filter(o => {
      if (!['new', 'submitted', 'working', 'partially_filled'].includes(o.status)) return false;
      const age = Date.now() - new Date(o.requested_at).getTime();
      return age > 300_000 && (o.replace_count ?? 0) >= 3;
    }).length;
    if (stuckCount > 0) {
      result.push({
        id: 'stuck-orders',
        severity: 'critical',
        icon: <AlertTriangle className="w-3.5 h-3.5" />,
        message: `${stuckCount} stuck order${stuckCount > 1 ? 's' : ''} — max reprices reached, manual intervention needed`,
      });
    }

    // API degraded
    if (healthSummary.status === 'DEGRADED') {
      result.push({
        id: 'degraded',
        severity: 'warning',
        icon: <Radio className="w-3.5 h-3.5" />,
        message: `System degraded: ${healthSummary.reason}`,
      });
    }

    // Repeated rejects (3+ in last 10 minutes)
    const recentRejects = (cryptoOrders ?? []).filter(o => {
      if (o.status !== 'rejected') return false;
      const age = Date.now() - new Date(o.requested_at).getTime();
      return age < 600_000;
    }).length;
    if (recentRejects >= 3) {
      result.push({
        id: 'repeated-rejects',
        severity: 'warning',
        icon: <XCircle className="w-3.5 h-3.5" />,
        message: `${recentRejects} orders rejected in last 10 minutes`,
      });
    }

    return result;
  }, [cryptoOrders, healthSummary]);

  if (alerts.length === 0) return null;

  return (
    <div className="space-y-2">
      {alerts.map(alert => (
        <div
          key={alert.id}
          className={cn(
            'flex items-center gap-2.5 px-4 py-2.5 border text-xs font-medium',
            alert.severity === 'critical'
              ? 'bg-loss/10 border-loss/30 text-loss'
              : 'bg-warning/10 border-warning/30 text-warning'
          )}
        >
          {alert.icon}
          <span>{alert.message}</span>
        </div>
      ))}
    </div>
  );
}
