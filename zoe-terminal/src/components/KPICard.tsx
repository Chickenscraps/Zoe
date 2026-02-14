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
    <div
      className={cn(
        "bg-paper-100/80 border-2 border-earth-700/20 relative overflow-hidden p-5 card-stagger",
        className,
      )}
      style={{
        borderRadius: 0,
        boxShadow: '3px 3px 0 rgba(69, 43, 39, 0.14)',
        ...style,
      }}
    >
      {/* Inset highlight for SNES window feel */}
      <div className="absolute inset-0 pointer-events-none" style={{ boxShadow: 'inset 1px 1px 0 rgba(255,255,255,0.3)' }} />

      <div className="flex justify-between items-start mb-3 relative">
        <span className="font-pixel text-[0.4rem] text-text-muted uppercase tracking-[0.12em]">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-earth-700/30" />}
      </div>

      <div className="flex items-baseline gap-2 relative">
        <span className={cn(
          "text-[1.75rem] font-extrabold text-earth-700 tracking-tight tabular-nums leading-none",
          trendDir === 'up' && "stat-glow-green",
          trendDir === 'down' && "stat-glow-red",
        )}>{value}</span>
        {trend && (
          <span className={cn(
            "font-pixel text-[0.3rem] px-2 py-0.5 tracking-wider uppercase tabular-nums border-2",
            trendDir === 'up' && "bg-profit/12 text-profit border-profit/25",
            trendDir === 'down' && "bg-loss/12 text-loss border-loss/25",
            trendDir === 'neutral' && "bg-earth-700/5 text-text-muted border-earth-700/10"
          )} style={{ borderRadius: 0 }}>
            {trend}
          </span>
        )}
      </div>

      {subValue && (
        <div className="mt-2.5 text-sm font-medium text-text-secondary flex items-center gap-1.5 relative">
          <div className="w-1.5 h-1.5 bg-sakura-500/50" style={{ borderRadius: 0 }} />
          {subValue}
        </div>
      )}
    </div>
  );
}
