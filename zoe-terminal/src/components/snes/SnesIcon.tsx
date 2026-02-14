import { cn } from '../../lib/utils';

// Individual icon PNGs from PixelChill kit
import arrowDown from '../../assets/sakura/icons/arrow_down.png';
import arrowUp from '../../assets/sakura/icons/arrow_up.png';
import bell from '../../assets/sakura/icons/bell.png';
import blossom from '../../assets/sakura/icons/blossom.png';
import check from '../../assets/sakura/icons/check.png';
import cross from '../../assets/sakura/icons/cross.png';
import filter from '../../assets/sakura/icons/filter.png';
import folder from '../../assets/sakura/icons/folder.png';
import house from '../../assets/sakura/icons/house.png';
import lantern from '../../assets/sakura/icons/lantern.png';
import minus from '../../assets/sakura/icons/minus.png';
import paintbrush from '../../assets/sakura/icons/paintbrush.png';
import plus from '../../assets/sakura/icons/plus.png';
import profile from '../../assets/sakura/icons/profile.png';
import scroll from '../../assets/sakura/icons/scroll.png';
import search from '../../assets/sakura/icons/search.png';
import settings from '../../assets/sakura/icons/settings.png';
import sparkle from '../../assets/sakura/icons/sparkle.png';
import terminal from '../../assets/sakura/icons/terminal.png';
import warning from '../../assets/sakura/icons/warning.png';

const ICON_MAP = {
  'arrow-down': arrowDown,
  'arrow-up': arrowUp,
  bell,
  blossom,
  check,
  cross,
  filter,
  folder,
  house,
  lantern,
  minus,
  paintbrush,
  plus,
  profile,
  scroll,
  search,
  settings,
  sparkle,
  terminal,
  warning,
} as const;

export type SnesIconName = keyof typeof ICON_MAP;

interface SnesIconProps {
  name: SnesIconName;
  size?: number;
  className?: string;
}

/**
 * Renders a PixelChill pixel icon at the given size.
 * Uses image-rendering: pixelated for crisp scaling.
 */
export default function SnesIcon({ name, size = 16, className }: SnesIconProps) {
  return (
    <img
      src={ICON_MAP[name]}
      alt={name}
      width={size}
      height={size}
      className={cn('inline-block', className)}
      style={{ imageRendering: 'pixelated' }}
    />
  );
}
