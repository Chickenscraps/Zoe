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
}

export function KPICard({ label, value, trend, trendDir, icon: Icon, subValue, className }: KPICardProps) {
  return (
    <div className={cn("card-premium p-6", className)}>
      <div className="flex justify-between items-start mb-3">
        <span className="text-text-muted text-[10px] font-black uppercase tracking-[0.1em]">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-text-muted/50" />}
      </div>
      
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-black text-white tracking-tighter tabular-nums">{value}</span>
        {trend && (
          <span className={cn(
            "text-[10px] font-black px-2 py-0.5 rounded-full tracking-wider uppercase",
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
    </div>
  );
}
