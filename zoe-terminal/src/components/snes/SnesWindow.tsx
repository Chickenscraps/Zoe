import { cn } from '../../lib/utils';
import windowKit from '../../assets/sakura/overlays/window_kit.png';

interface SnesWindowProps {
  title?: string;
  variant?: 'normal' | 'focused' | 'disabled' | 'danger';
  children: React.ReactNode;
  className?: string;
  noPad?: boolean;
}

const VARIANT_STYLES = {
  normal: 'border-earth-700/25 bg-surface-base',
  focused: 'border-sakura-500 bg-surface-base',
  disabled: 'border-earth-700/10 bg-surface-highlight/50 opacity-60',
  danger: 'border-loss/50 bg-surface-base',
} as const;

/**
 * 9-slice style pixel window panel using PixelChill window kit.
 * Uses the window_kit.png as a border-image for authentic pixel framing.
 * Variants: normal, focused (sakura border), disabled (dimmed), danger (red border).
 */
export default function SnesWindow({ title, variant = 'normal', children, className, noPad }: SnesWindowProps) {
  return (
    <div
      className={cn(
        'border-2 overflow-hidden',
        VARIANT_STYLES[variant],
        className,
      )}
      style={{
        borderRadius: 0,
        borderImage: variant === 'normal' ? `url(${windowKit}) 12 fill / 12px / 0 stretch` : undefined,
        borderImageRepeat: 'stretch',
        imageRendering: 'pixelated',
        boxShadow: variant === 'focused'
          ? '3px 3px 0 rgba(239, 163, 168, 0.20)'
          : '3px 3px 0 rgba(69, 43, 39, 0.15)',
      }}
    >
      {/* Title bar — mimics SNES window header */}
      {title && (
        <div
          className="bg-earth-700/12 border-b-2 border-earth-700/15 px-4 py-2 flex items-center gap-2"
          style={{
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.35)',
          }}
        >
          {/* Corner studs */}
          <span className="w-2 h-2 bg-earth-700/20 border border-earth-700/10 flex-shrink-0" aria-hidden />
          <span className="font-pixel text-[0.5rem] uppercase tracking-[0.12em] text-earth-700/80 flex-1">
            {title}
          </span>
          <span className="w-2 h-2 bg-earth-700/20 border border-earth-700/10 flex-shrink-0" aria-hidden />
        </div>
      )}
      {/* Content area with inset highlight */}
      <div
        className={noPad ? '' : 'p-5'}
        style={{
          boxShadow: 'inset 1px 1px 0 rgba(255,255,255,0.3)',
        }}
      >
        {children}
      </div>
    </div>
  );
}
