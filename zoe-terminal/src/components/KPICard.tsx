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
    <div className={cn("bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] relative overflow-hidden p-5 card-stagger", className)} style={style}>
      <div className="flex justify-between items-start mb-3">
        <span className="font-pixel text-[0.35rem] text-text-muted uppercase tracking-[0.1em]">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-earth-700/25" />}
      </div>

      <div className="flex items-baseline gap-2">
        <span className={cn(
          "text-2xl font-bold text-earth-700 tracking-tighter tabular-nums",
          trendDir === 'up' && "stat-glow-green",
          trendDir === 'down' && "stat-glow-red",
        )}>{value}</span>
        {trend && (
          <span className={cn(
            "font-pixel text-[0.3rem] px-2 py-0.5 rounded-[4px] tracking-wider uppercase tabular-nums",
            trendDir === 'up' && "bg-profit/10 text-profit border border-profit/20",
            trendDir === 'down' && "bg-loss/10 text-loss border border-loss/20",
            trendDir === 'neutral' && "bg-earth-700/5 text-text-muted border border-earth-700/10"
          )}>
            {trend}
          </span>
        )}
      </div>

      {subValue && (
        <div className="mt-2 text-[10px] font-medium text-text-muted flex items-center gap-1.5">
          <div className="w-1 h-1 rounded-full bg-sakura-500/40" />
          {subValue}
        </div>
      )}
    </div>
  );
}
