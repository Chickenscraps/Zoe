import { Link, useLocation } from 'react-router-dom';
import { cn } from '../../lib/utils';
import type { LucideIcon } from 'lucide-react';

interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
}

interface SnesNavProps {
  items: NavItem[];
  collapsed?: boolean;
}

/**
 * Pixel-styled sidebar navigation.
 * Active item gets a sakura highlight bar and a blinking triangle cursor.
 * Zero border-radius, pixel aesthetic throughout.
 */
export default function SnesNav({ items, collapsed = false }: SnesNavProps) {
  const location = useLocation();

  return (
    <nav className="flex flex-col gap-0.5 py-3 px-2">
      {items.map((item) => {
        const active =
          item.path === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(item.path);
        const Icon = item.icon;

        return (
          <Link
            key={item.path}
            to={item.path}
            className={cn(
              'group flex items-center gap-3 px-3 py-2.5 transition-colors duration-100 relative border-2',
              active
                ? 'bg-sakura-500/18 text-earth-700 border-sakura-500/30'
                : 'text-text-secondary hover:bg-sakura-500/8 hover:text-text-primary border-transparent hover:border-earth-700/8',
            )}
            style={{ borderRadius: 0 }}
          >
            {/* Blinking cursor triangle for active item */}
            {active && (
              <span
                className="absolute left-1 text-sakura-700 font-pixel text-[0.5rem] animate-pulse"
                aria-hidden
              >
                &#9654;
              </span>
            )}

            <Icon
              size={collapsed ? 20 : 16}
              className={cn(
                'flex-shrink-0',
                active ? 'text-sakura-700' : 'text-text-muted group-hover:text-text-secondary',
                collapsed ? 'mx-auto' : 'ml-4',
              )}
            />

            {!collapsed && (
              <span
                className={cn(
                  'font-pixel text-[0.5rem] uppercase tracking-[0.08em]',
                  active ? 'text-earth-700 font-bold' : '',
                )}
              >
                {item.label}
              </span>
            )}

            {/* Active highlight bar — pixel style */}
            {active && (
              <span
                className="absolute right-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-sakura-500"
                style={{ borderRadius: 0 }}
                aria-hidden
              />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
