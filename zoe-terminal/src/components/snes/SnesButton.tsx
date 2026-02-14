import { cn } from '../../lib/utils';

interface SnesButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: 'sm' | 'md' | 'lg';
  variant?: 'primary' | 'secondary' | 'danger';
}

const SIZE_CLASSES = {
  sm: 'px-3 py-1.5 text-[0.45rem]',
  md: 'px-5 py-2 text-[0.5rem]',
  lg: 'px-7 py-2.5 text-[0.55rem]',
} as const;

const VARIANT_CLASSES = {
  primary: 'bg-earth-700 text-cream-100 hover:bg-earth-700/90 border-earth-700',
  secondary: 'bg-surface-highlight text-earth-700 hover:bg-surface-highlight/80 border-earth-700/25',
  danger: 'bg-loss text-white hover:bg-loss/90 border-loss',
} as const;

/**
 * Pixel-styled SNES button with crisp pixel shadow and press feedback.
 * Uses pixel font, zero border-radius, and active state push-down.
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
        'font-pixel uppercase tracking-[0.08em] border-2',
        'transition-all duration-75',
        'active:translate-y-[2px] active:translate-x-[1px]',
        SIZE_CLASSES[size],
        VARIANT_CLASSES[variant],
        disabled && 'opacity-50 cursor-not-allowed active:translate-y-0 active:translate-x-0',
        className,
      )}
      style={{
        borderRadius: 0,
        boxShadow: disabled
          ? 'none'
          : '3px 3px 0 rgba(69, 43, 39, 0.20)',
      }}
      onMouseDown={(e) => {
        if (!disabled) {
          (e.currentTarget as HTMLButtonElement).style.boxShadow = 'inset 2px 2px 0 rgba(69, 43, 39, 0.20)';
        }
      }}
      onMouseUp={(e) => {
        if (!disabled) {
          (e.currentTarget as HTMLButtonElement).style.boxShadow = '3px 3px 0 rgba(69, 43, 39, 0.20)';
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          (e.currentTarget as HTMLButtonElement).style.boxShadow = '3px 3px 0 rgba(69, 43, 39, 0.20)';
        }
      }}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
