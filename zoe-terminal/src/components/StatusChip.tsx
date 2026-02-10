import { cn } from '../lib/utils';
import { cva, type VariantProps } from 'class-variance-authority';
import type { LucideIcon } from 'lucide-react';

const statusChipVariants = cva(
  "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
  {
    variants: {
      status: {
        ok: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
        warning: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
        error: "bg-red-500/10 text-red-500 border-red-500/20",
        down: "bg-gray-500/10 text-gray-500 border-gray-500/20",
        neutral: "bg-surface-highlight text-text-secondary border-border",
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
