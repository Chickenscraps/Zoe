import type { LucideIcon } from 'lucide-react';
import { cn } from '../lib/utils';

interface KPICardProps {
  label: string;
  value: string;
  trend?: string;
  trendDir?: 'up' | 'down' | 'neutral';
  icon?: LucideIcon;
  subValue?: string;
  className?: string;
  style?: React.CSSProperties;
}

export function KPICard({ label, value, trend, trendDir, icon: Icon, subValue, className, style }: KPICardProps) {
  return (
    <div className={cn("card-glass card-shimmer-sweep relative overflow-hidden p-6", className)} style={style}>
      <div className="flex justify-between items-start mb-3">
        <span className="text-text-muted text-[10px] font-semibold uppercase tracking-[0.15em]">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-text-muted/40" />}
      </div>

      <div className="flex items-baseline gap-2">
        <span className={cn(
          "text-3xl font-bold text-white tracking-tighter tabular-nums",
          trendDir === 'up' && "stat-glow-green",
          trendDir === 'down' && "stat-glow-red",
        )}>{value}</span>
        {trend && (
          <span className={cn(
            "text-[10px] font-semibold px-2 py-0.5 rounded-full tracking-wider uppercase tabular-nums",
            trendDir === 'up' && "bg-profit/10 text-profit border border-profit/20",
            trendDir === 'down' && "bg-loss/10 text-loss border border-loss/20",
            trendDir === 'neutral' && "bg-white/5 text-text-muted border border-white/10"
          )}>
            {trend}
          </span>
        )}
      </div>

      {subValue && (
        <div className="mt-2 text-[11px] font-medium text-text-muted flex items-center gap-1.5">
          <div className="w-1 h-1 rounded-full bg-border-strong" />
          {subValue}
        </div>
      )}

      {/* Bottom shine */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
    </div>
  );
}
