import { useState } from 'react';
import { cn } from '../../lib/utils';

// Individual button state PNGs from PixelChill kit
import smNormal from '../../assets/sakura/buttons/small_normal.png';
import smHover from '../../assets/sakura/buttons/small_hover.png';
import smPressed from '../../assets/sakura/buttons/small_pressed.png';
import smDisabled from '../../assets/sakura/buttons/small_disabled.png';
import smSelected from '../../assets/sakura/buttons/small_selected.png';

import mdNormal from '../../assets/sakura/buttons/medium_normal.png';
import mdHover from '../../assets/sakura/buttons/medium_hover.png';
import mdPressed from '../../assets/sakura/buttons/medium_pressed.png';
import mdDisabled from '../../assets/sakura/buttons/medium_disabled.png';
import mdSelected from '../../assets/sakura/buttons/medium_selected.png';

import lgNormal from '../../assets/sakura/buttons/large_normal.png';
import lgHover from '../../assets/sakura/buttons/large_hover.png';
import lgPressed from '../../assets/sakura/buttons/large_pressed.png';
import lgDisabled from '../../assets/sakura/buttons/large_disabled.png';
import lgSelected from '../../assets/sakura/buttons/large_selected.png';

interface SnesButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: 'sm' | 'md' | 'lg';
  variant?: 'primary' | 'secondary' | 'danger';
  selected?: boolean;
}

const BUTTON_ASSETS = {
  sm: { normal: smNormal, hover: smHover, pressed: smPressed, disabled: smDisabled, selected: smSelected, h: 63, w: 177 },
  md: { normal: mdNormal, hover: mdHover, pressed: mdPressed, disabled: mdDisabled, selected: mdSelected, h: 74, w: 252 },
  lg: { normal: lgNormal, hover: lgHover, pressed: lgPressed, disabled: lgDisabled, selected: lgSelected, h: 92, w: 276 },
} as const;

const SIZE_LABEL = {
  sm: 'text-[0.45rem] min-h-[32px] px-4 py-1',
  md: 'text-[0.5rem] min-h-[37px] px-6 py-1.5',
  lg: 'text-[0.55rem] min-h-[46px] px-8 py-2',
} as const;

const VARIANT_TEXT = {
  primary: 'text-earth-700',
  secondary: 'text-earth-700/80',
  danger: 'text-loss',
} as const;

/**
 * Pixel-styled SNES button using PixelChill cut PNG assets.
 * Swaps background image on hover/press/disabled for authentic pixel-art states.
 * Text is rendered on top of the button image via absolute positioning.
 */
export default function SnesButton({
  size = 'md',
  variant = 'primary',
  selected = false,
  className,
  children,
  disabled,
  ...props
}: SnesButtonProps) {
  const [hovered, setHovered] = useState(false);
  const [pressed, setPressed] = useState(false);

  const assets = BUTTON_ASSETS[size];

  let bgSrc = assets.normal;
  if (disabled) bgSrc = assets.disabled;
  else if (selected) bgSrc = assets.selected;
  else if (pressed) bgSrc = assets.pressed;
  else if (hovered) bgSrc = assets.hover;

  return (
    <button
      className={cn(
        'relative font-pixel uppercase tracking-[0.08em] border-0 bg-transparent cursor-pointer inline-flex items-center justify-center',
        SIZE_LABEL[size],
        VARIANT_TEXT[variant],
        disabled && 'opacity-70 cursor-not-allowed',
        className,
      )}
      style={{
        backgroundImage: `url(${bgSrc})`,
        backgroundSize: '100% 100%',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center',
        imageRendering: 'pixelated',
        borderRadius: 0,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setPressed(false); }}
      onMouseDown={() => !disabled && setPressed(true)}
      onMouseUp={() => setPressed(false)}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
