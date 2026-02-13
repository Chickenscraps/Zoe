import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  History,
  Scan,
  Map,
  BrainCircuit,
  Activity,
  Settings,
  Menu,
  X,
  Layers,
  BarChart3,
  Shield,
} from 'lucide-react';
import { cn, formatCurrency } from '../lib/utils';
import { useDashboardData } from '../hooks/useDashboardData';
import { MODE, isPaper, isLive } from '../lib/mode';

const NAV_ITEMS = [
  { label: 'Overview', path: '/', icon: LayoutDashboard },
  { label: 'Positions', path: '/positions', icon: Briefcase },
  { label: 'Trades', path: '/trades', icon: History },
  { label: 'Structure', path: '/structure', icon: Layers },
  { label: 'Scanner', path: '/scanner', icon: Scan },
  { label: 'Charts', path: '/charts', icon: BarChart3 },
  { label: 'Consensus', path: '/consensus', icon: Shield },
  { label: 'Plan', path: '/plan', icon: Map },
];

/** Items hidden behind a collapsible "System" menu on mobile */
const SYSTEM_ITEMS = [
  { label: 'Thoughts', path: '/thoughts', icon: BrainCircuit },
  { label: 'Health', path: '/health', icon: Activity },
  { label: 'Settings', path: '/settings', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { cryptoCash, accountOverview, healthSummary } = useDashboardData();

  const equity = cryptoCash?.buying_power ?? cryptoCash?.cash_available ?? accountOverview?.equity ?? 0;

  const closeSidebar = () => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  // Close sidebar on route change (mobile)
  useEffect(() => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  }, [location.pathname]);

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    if (sidebarOpen && window.innerWidth < 1024) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [sidebarOpen]);

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col relative">
      <div className="noise-overlay" />

      {/* Mode Banner — compact on mobile */}
      <div className={cn(
        "w-full text-center py-1 sm:py-1.5 text-[10px] sm:text-[11px] font-black tracking-[0.25em] uppercase z-[60] relative select-none safe-top",
        isPaper
          ? "bg-profit/15 text-profit border-b border-profit/20"
          : "bg-loss/15 text-loss border-b border-loss/20 animate-pulse"
      )}>
        {isPaper ? "◆ PAPER ◆" : "◆ LIVE ◆"}
      </div>

      {/* ── Mobile Full-Screen Menu ── */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden bg-background/95 backdrop-blur-xl flex flex-col animate-in fade-in duration-150">
          {/* Close bar */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-border/40">
            <h1 className="text-lg font-bold tracking-tighter text-white">
              ZOE<span className="text-text-muted">_</span>TERMINAL
            </h1>
            <button
              className="min-w-[48px] min-h-[48px] flex items-center justify-center rounded-full bg-surface-highlight text-white hover:bg-white/10 transition-colors"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close menu"
            >
              <X size={24} />
            </button>
          </div>

          {/* Two-column nav grid */}
          <div className="flex-1 overflow-y-auto p-5 safe-bottom">
            <div className="grid grid-cols-2 gap-3">
              {NAV_ITEMS.map((item) => {
                const isActive = location.pathname === item.path;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={closeSidebar}
                    className={cn(
                      "flex flex-col items-center justify-center gap-2 p-4 rounded-cards border text-sm font-semibold transition-all duration-200 min-h-[88px]",
                      isActive
                        ? "bg-surface-highlight text-white border-white/20 shadow-soft"
                        : "bg-surface/60 text-text-secondary border-border/40 hover:text-white hover:bg-surface-highlight/50"
                    )}
                  >
                    <Icon className={cn("w-6 h-6 shrink-0", isActive ? "text-profit" : "")} />
                    {item.label}
                  </Link>
                );
              })}
            </div>

            {/* System section */}
            <div className="mt-5 pt-4 border-t border-border/30">
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-3 px-1">System</div>
              <div className="grid grid-cols-3 gap-3">
                {SYSTEM_ITEMS.map((item) => {
                  const isActive = location.pathname === item.path;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      onClick={closeSidebar}
                      className={cn(
                        "flex flex-col items-center justify-center gap-2 p-3 rounded-cards border text-xs font-semibold transition-all duration-200 min-h-[72px]",
                        isActive
                          ? "bg-surface-highlight text-white border-white/20 shadow-soft"
                          : "bg-surface/60 text-text-secondary border-border/40 hover:text-white hover:bg-surface-highlight/50"
                      )}
                    >
                      <Icon className={cn("w-5 h-5 shrink-0", isActive ? "text-profit" : "")} />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>

            {/* Node Instance footer */}
            <div className="mt-6">
              <div className="bg-surface-base/50 p-3 rounded-cards border border-border flex flex-col gap-1">
                <div className="text-[10px] uppercase tracking-widest text-text-muted font-medium">Node Instance</div>
                <div className="text-xs font-mono text-white truncate opacity-80">primary-v4-live</div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-1 relative">
      {/* Sidebar — desktop only */}
      <aside
        className="hidden lg:flex fixed inset-y-0 left-0 z-50 w-64 bg-surface border-r border-border lg:relative shadow-crisp flex-col"
      >
        <div className="h-20 flex items-center px-8 border-b border-border">
          <h1 className="text-xl font-bold tracking-tighter text-white">
            ZOE<span className="text-text-muted">_</span>TERMINAL
          </h1>
        </div>

        <nav className="p-4 space-y-1 overflow-y-auto flex-1">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-3 px-4 py-2.5 rounded-btns text-sm font-semibold transition-all duration-200 min-h-[44px]",
                  isActive
                    ? "bg-surface-highlight text-white shadow-soft border-l-[3px] border-l-white/30"
                    : "text-text-secondary hover:text-white hover:bg-white/[0.03] border-l-[3px] border-l-transparent"
                )}
              >
                <Icon className={cn("w-4 h-4 shrink-0", isActive ? "text-profit" : "")} />
                {item.label}
              </Link>
            );
          })}

          {SYSTEM_ITEMS.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-3 px-4 py-2.5 rounded-btns text-sm font-semibold transition-all duration-200 min-h-[44px]",
                  isActive
                    ? "bg-surface-highlight text-white shadow-soft border-l-[3px] border-l-white/30"
                    : "text-text-secondary hover:text-white hover:bg-white/[0.03] border-l-[3px] border-l-transparent"
                )}
              >
                <Icon className={cn("w-4 h-4 shrink-0", isActive ? "text-profit" : "")} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-6 safe-bottom">
          <div className="bg-surface-base/50 p-4 rounded-cards border border-border flex flex-col gap-1">
             <div className="text-[10px] uppercase tracking-widest text-text-muted font-medium">Node Instance</div>
             <div className="text-xs font-mono text-white truncate opacity-80">primary-v4-live</div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 sm:h-16 lg:h-20 border-b border-border bg-background/40 backdrop-blur-xl sticky top-0 z-40 flex items-center justify-between px-3 sm:px-6 lg:px-8 shadow-crisp">
          <button
            className="lg:hidden min-w-[44px] min-h-[44px] flex items-center justify-center text-text-secondary hover:text-white transition-colors -ml-1"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle navigation"
          >
            {sidebarOpen ? <X size={22} /> : <Menu size={22} />}
          </button>

          <div className="flex items-center gap-3 sm:gap-6 ml-auto">
            <div className="flex items-center gap-3 sm:gap-6 text-sm">
               <div className="flex flex-col items-end">
                 <span className="text-[9px] sm:text-[10px] text-text-muted uppercase font-bold tracking-widest leading-tight">Equity</span>
                 <span className="font-mono text-base sm:text-lg font-black text-white">{formatCurrency(equity)}</span>
               </div>
               <div className="h-8 w-px bg-border hidden sm:block" />
               {isPaper ? (
                 <div className="hidden sm:block bg-profit/10 border border-profit/20 text-profit px-3 py-1 rounded-full text-[10px] font-black tracking-widest uppercase">
                   Paper Mode
                 </div>
               ) : (
                 <div className="hidden sm:block bg-loss/10 border border-loss/20 text-loss px-3 py-1 rounded-full text-[10px] font-black tracking-widest uppercase animate-pulse">
                   LIVE
                 </div>
               )}
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-12 overflow-auto relative z-10 safe-bottom">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
      </div>
    </div>
  );
}
