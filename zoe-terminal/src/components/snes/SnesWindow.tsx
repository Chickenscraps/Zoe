import { cn } from '../../lib/utils';

interface SnesWindowProps {
  title?: string;
  variant?: 'normal' | 'focused' | 'disabled' | 'danger';
  children: React.ReactNode;
  className?: string;
}

const VARIANT_STYLES = {
  normal: 'border-earth-700/20 bg-surface-base',
  focused: 'border-sakura-500 bg-surface-base shadow-[0_0_12px_rgba(239,163,168,0.15)]',
  disabled: 'border-earth-700/10 bg-surface-highlight/50 opacity-60',
  danger: 'border-loss/40 bg-surface-base',
} as const;

/**
 * 9-slice style pixel window panel.
 * Uses CSS borders styled to evoke SNES window kits.
 * Variants: normal, focused (sakura glow), disabled (dimmed), danger (red border).
 */
export default function SnesWindow({ title, variant = 'normal', children, className }: SnesWindowProps) {
  return (
    <div
      className={cn(
        'border-2 rounded-[4px] overflow-hidden',
        VARIANT_STYLES[variant],
        className,
      )}
    >
      {title && (
        <div className="bg-earth-700/10 border-b border-earth-700/15 px-3 py-1.5 flex items-center gap-2">
          <span className="font-pixel text-[0.45rem] uppercase tracking-[0.1em] text-earth-700/70">
            {title}
          </span>
        </div>
      )}
      <div className="p-4">
        {children}
      </div>
    </div>
  );
}
