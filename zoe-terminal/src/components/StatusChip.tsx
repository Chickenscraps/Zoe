import { cn } from '../lib/utils';
import { cva, type VariantProps } from 'class-variance-authority';
import type { LucideIcon } from 'lucide-react';

const statusChipVariants = cva(
  "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-[0.1em] border",
  {
    variants: {
      status: {
        ok: "bg-profit/10 text-profit border-profit/20",
        warning: "bg-warning/10 text-warning border-warning/20",
        error: "bg-loss/10 text-loss border-loss/20",
        down: "bg-white/5 text-text-muted border-white/10",
        neutral: "bg-surface-highlight/50 text-white border-border",
      },
    },
    defaultVariants: {
      status: "neutral",
    },
  }
);

interface StatusChipProps extends VariantProps<typeof statusChipVariants> {
  label: string;
  icon?: LucideIcon;
  className?: string;
}

export function StatusChip({ status, label, icon: Icon, className }: StatusChipProps) {
  return (
    <span className={cn(statusChipVariants({ status }), className)}>
      {Icon && <Icon className="w-3 h-3" />}
      {label}
    </span>
  );
}
