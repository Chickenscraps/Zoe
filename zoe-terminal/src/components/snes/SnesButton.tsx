import { cn } from '../../lib/utils';

interface SnesButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: 'sm' | 'md' | 'lg';
  variant?: 'primary' | 'secondary' | 'danger';
}

const SIZE_CLASSES = {
  sm: 'px-3 py-1 text-[0.45rem]',
  md: 'px-5 py-2 text-[0.5rem]',
  lg: 'px-7 py-2.5 text-[0.55rem]',
} as const;

const VARIANT_CLASSES = {
  primary: 'bg-earth-700 text-cream-100 hover:bg-earth-700/90 border-earth-700',
  secondary: 'bg-surface-highlight text-earth-700 hover:bg-surface-highlight/80 border-earth-700/20',
  danger: 'bg-loss text-white hover:bg-loss/90 border-loss',
} as const;

/**
 * Pixel-styled SNES button with press feedback.
 * Uses pixel font, sharp 4px corners, and active state push-down.
 */
export default function SnesButton({
  size = 'md',
  variant = 'primary',
  className,
  children,
  disabled,
  ...props
}: SnesButtonProps) {
  return (
    <button
      className={cn(
        'font-pixel uppercase tracking-[0.08em] border-2 rounded-[4px]',
        'transition-all duration-75',
        'active:translate-y-[1px] active:shadow-none',
        'shadow-[0_2px_0_rgba(69,43,39,0.2)]',
        SIZE_CLASSES[size],
        VARIANT_CLASSES[variant],
        disabled && 'opacity-50 cursor-not-allowed active:translate-y-0',
        className,
      )}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
