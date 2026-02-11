import { useState } from 'react';
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
} from 'lucide-react';
import { cn, formatCurrency } from '../lib/utils';
import { useDashboardData } from '../hooks/useDashboardData';

const NAV_ITEMS = [
  { label: 'Overview', path: '/', icon: LayoutDashboard },
  { label: 'Positions', path: '/positions', icon: Briefcase },
  { label: 'Trades', path: '/trades', icon: History },
  { label: 'Structure', path: '/structure', icon: Layers },
  { label: 'Scanner', path: '/scanner', icon: Scan },
  { label: 'Plan', path: '/plan', icon: Map },
  { label: 'Thoughts', path: '/thoughts', icon: BrainCircuit },
  { label: 'Health', path: '/health', icon: Activity },
  { label: 'Settings', path: '/settings', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { cryptoCash, accountOverview, healthSummary } = useDashboardData();

  // Dynamic equity: prefer crypto cash snapshot, fall back to account overview, then default
  const equity = cryptoCash?.cash_available ?? accountOverview?.equity ?? 0;

  // Dynamic mode: if reconciliation data exists and is fresh, we're live; otherwise paper
  const isLive = healthSummary.status === 'LIVE' && !healthSummary.stale;
  const tradingMode = isLive ? 'live' : 'paper';

  const closeSidebar = () => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-text-primary flex relative">
      <div className="noise-overlay" />
      
      {/* Sidebar */}
      <aside 
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-surface border-r border-border transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0 shadow-crisp",
          !sidebarOpen && "-translate-x-full"
        )}
      >
        <div className="h-20 flex items-center px-8 border-b border-border">
          <h1 className="text-xl font-bold tracking-tighter text-white">
            ZOE<span className="text-text-muted">_</span>TERMINAL
          </h1>
        </div>
        
        <nav className="p-4 space-y-2">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-3 px-4 py-2.5 rounded-btns text-sm font-semibold transition-all duration-200",
                  isActive
                    ? "bg-surface-highlight text-white shadow-soft border-l-[3px] border-l-white/30"
                    : "text-text-secondary hover:text-white hover:bg-white/[0.03] border-l-[3px] border-l-transparent"
                )}
              >
                <Icon className={cn("w-4 h-4", isActive ? "text-profit" : "")} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        
        <div className="absolute bottom-6 left-6 right-6">
          <div className="bg-surface-base/50 p-4 rounded-cards border border-border flex flex-col gap-1">
             <div className="text-[10px] uppercase tracking-widest text-text-muted font-medium">Node Instance</div>
             <div className="text-xs font-mono text-white truncate opacity-80">primary-v4-live</div>
          </div>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-md"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-20 border-b border-border bg-background/40 backdrop-blur-xl sticky top-0 z-40 flex items-center justify-between px-8 shadow-crisp">
          <button 
            className="lg:hidden p-2 -ml-2 text-text-secondary hover:text-white transition-colors"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          
          <div className="flex items-center gap-6 ml-auto">
            <div className="flex items-center gap-6 text-sm">
               <div className="flex flex-col items-end">
                 <span className="text-[10px] text-text-muted uppercase font-bold tracking-widest leading-tight">Net Equity</span>
                 <span className="font-mono text-lg font-black text-white">{formatCurrency(equity)}</span>
               </div>
               <div className="h-8 w-px bg-border hidden xs:block" />
               {tradingMode === 'paper' ? (
                 <div className="hidden xs:block bg-profit/10 border border-profit/20 text-profit px-3 py-1 rounded-full text-[10px] font-black tracking-widest uppercase">
                   Paper Mode
                 </div>
               ) : (
                 <div className="hidden xs:block bg-loss/10 border border-loss/20 text-loss px-3 py-1 rounded-full text-[10px] font-black tracking-widest uppercase animate-pulse">
                   LIVE
                 </div>
               )}
            </div>
          </div>
        </header>

        <main className="flex-1 p-8 lg:p-12 overflow-auto relative z-10">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
