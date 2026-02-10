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
    <div className={cn("bg-surface border border-border rounded-lg p-5", className)}>
      <div className="flex justify-between items-start mb-2">
        <span className="text-text-secondary text-xs font-medium uppercase tracking-wider">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-text-muted" />}
      </div>
      
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-text-primary">{value}</span>
        {trend && (
          <span className={cn(
            "text-xs font-medium px-1.5 py-0.5 rounded",
            trendDir === 'up' && "bg-profit/10 text-profit",
            trendDir === 'down' && "bg-loss/10 text-loss",
            trendDir === 'neutral' && "bg-text-secondary/10 text-text-secondary"
          )}>
            {trend}
          </span>
        )}
      </div>
      
      {subValue && (
        <div className="mt-1 text-xs text-text-muted">
          {subValue}
        </div>
      )}
    </div>
  );
}
