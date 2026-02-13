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

      <div className="flex flex-1 relative">
      {/* Sidebar — drawer on mobile */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-[280px] sm:w-64 bg-surface border-r border-border transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0 shadow-crisp safe-left",
          sidebarOpen ? "translate-x-0 drawer-enter" : "-translate-x-full"
        )}
      >
        <div className="h-14 sm:h-16 lg:h-20 flex items-center justify-between px-5 sm:px-6 lg:px-8 border-b border-border">
          <h1 className="text-lg sm:text-xl font-bold tracking-tighter text-white">
            ZOE<span className="text-text-muted">_</span>TERMINAL
          </h1>
          <button
            className="lg:hidden min-w-[44px] min-h-[44px] flex items-center justify-center text-text-secondary hover:text-white transition-colors -mr-2"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="p-3 sm:p-4 space-y-1 overflow-y-auto max-h-[calc(100vh-140px)] scroll-smooth-mobile">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;

            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 sm:py-2.5 rounded-btns text-sm font-semibold transition-all duration-200 min-h-[44px]",
                  isActive
                    ? "bg-surface-highlight text-white shadow-soft border-l-[3px] border-l-white/30"
                    : "text-text-secondary hover:text-white hover:bg-white/[0.03] border-l-[3px] border-l-transparent"
                )}
              >
                <Icon className={cn("w-[18px] h-[18px] sm:w-4 sm:h-4 shrink-0", isActive ? "text-profit" : "")} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-4 sm:bottom-6 left-4 sm:left-6 right-4 sm:right-6 safe-bottom">
          <div className="bg-surface-base/50 p-3 sm:p-4 rounded-cards border border-border flex flex-col gap-1">
             <div className="text-[10px] uppercase tracking-widest text-text-muted font-medium">Node Instance</div>
             <div className="text-xs font-mono text-white truncate opacity-80">primary-v4-live</div>
          </div>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/70 z-40 lg:hidden backdrop-blur-md"
          onClick={() => setSidebarOpen(false)}
        />
      )}

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
