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
 */
export default function SnesNav({ items, collapsed = false }: SnesNavProps) {
  const location = useLocation();

  return (
    <nav className="flex flex-col gap-0.5 py-2">
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
              'group flex items-center gap-3 px-3 py-2.5 rounded-[4px] transition-colors duration-100 relative',
              active
                ? 'bg-sakura-500/15 text-earth-700'
                : 'text-text-muted hover:bg-sakura-500/8 hover:text-text-primary',
            )}
          >
            {/* Blinking cursor triangle for active item */}
            {active && (
              <span
                className="absolute left-0.5 text-sakura-500 font-pixel text-[0.5rem] animate-pulse"
                aria-hidden
              >
                ▶
              </span>
            )}

            <Icon
              size={collapsed ? 20 : 16}
              className={cn(
                'flex-shrink-0',
                active ? 'text-sakura-700' : 'text-text-muted group-hover:text-text-secondary',
                collapsed ? 'mx-auto' : 'ml-3',
              )}
            />

            {!collapsed && (
              <span
                className={cn(
                  'font-pixel text-[0.45rem] uppercase tracking-[0.08em]',
                  active ? 'text-earth-700' : '',
                )}
              >
                {item.label}
              </span>
            )}

            {/* Active highlight bar */}
            {active && (
              <span
                className="absolute right-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-sakura-500 rounded-full"
                aria-hidden
              />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
