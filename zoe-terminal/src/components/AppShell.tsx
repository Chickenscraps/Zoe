import { useState, lazy, Suspense } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  History,
  Scan,
  BrainCircuit,
  Settings,
  Menu,
  X,
  BarChart3,
  LogOut,
  Bot,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useSystemHealth } from '../hooks/useSystemHealth';
import { useAuth } from '../lib/AuthContext';
import { useCopilotContext } from '../lib/CopilotContext';
import { ErrorBoundary } from './ErrorBoundary';
import { HealthCluster, CircuitBreakerBanner } from './SystemHealthIndicators';

const CopilotSidebar = lazy(() => import('./CopilotSidebar'));

const NAV_ITEMS = [
  { label: 'Overview', path: '/', icon: LayoutDashboard },
  { label: 'Activity', path: '/activity', icon: History },
  { label: 'Scanner', path: '/scanner', icon: Scan },
  { label: 'Charts', path: '/charts', icon: BarChart3 },
  { label: 'Intelligence', path: '/intelligence', icon: BrainCircuit },
  { label: 'Settings', path: '/settings', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { isGuest, logout } = useAuth();
  const { isOpen: copilotOpen, toggle: toggleCopilot } = useCopilotContext();
  const systemHealth = useSystemHealth();

  const closeSidebar = () => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  return (
    <div className="h-screen bg-background text-text-primary flex flex-col relative">
      {/* Guest Banner */}
      {isGuest && (
        <div className="w-full text-center py-1 text-[10px] font-bold tracking-[0.2em] uppercase z-[60] relative select-none bg-amber-800/10 text-amber-500/70 border-b border-amber-800/15">
          VIEW ONLY — Guest Access
        </div>
      )}

      {/* Circuit Breaker Banner */}
      <CircuitBreakerBanner health={systemHealth} />

      <div className="flex flex-1 relative overflow-hidden">
      {/* Desktop sidebar spacer */}
      <div className="hidden lg:block w-64 shrink-0" />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 sm:h-20 border-b border-border bg-background/40 backdrop-blur-xl sticky top-0 z-30 flex items-center justify-between px-3 sm:px-8 shadow-crisp">
          <div className="flex items-center gap-2">
            <button
              className="lg:hidden p-2 -ml-1 text-text-secondary hover:text-text-primary transition-colors z-[75] relative"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>

          <div className="flex items-center gap-2 sm:gap-6 ml-auto min-w-0">
            <div className="flex items-center gap-2 sm:gap-6 text-sm flex-wrap justify-end">
               {/* Health Indicators */}
               <div className="hidden sm:block">
                 <HealthCluster health={systemHealth} />
               </div>
               {/* Copilot Toggle */}
               <button
                 onClick={toggleCopilot}
                 className={cn(
                   "p-1.5 sm:p-2 rounded-full border transition-all",
                   copilotOpen
                     ? "bg-profit/15 text-profit border-profit/30"
                     : "bg-white/5 text-text-muted border-border hover:text-text-primary hover:border-text-primary/20"
                 )}
                 title={copilotOpen ? "Close Copilot (⌘K)" : "Open Copilot (⌘K)"}
               >
                 <Bot className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
               </button>
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-8 lg:p-12 overflow-auto relative z-10">
          <div className="max-w-7xl mx-auto">
            <ErrorBoundary fallbackMessage="This page encountered an error">
              {children}
            </ErrorBoundary>
          </div>

          {/* Credit Footer */}
          <div className="max-w-7xl mx-auto mt-16 pb-6 text-center">
            <div className="border-t border-border/30 pt-6">
              <p className="text-[10px] text-text-dim tracking-[0.15em] uppercase font-medium">
                Planned & Designed by Josh Andrewlavage | Tobie LLC
              </p>
            </div>
          </div>
        </main>
      </div>

      {/* Desktop copilot spacer */}
      {copilotOpen && <div className="hidden lg:block w-80 shrink-0" />}

      </div>

      {/* Copilot Sidebar */}
      <Suspense fallback={null}>
        <CopilotSidebar />
      </Suspense>

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-[70] w-64 bg-surface border-r border-border transform transition-transform duration-200 ease-in-out shadow-crisp",
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        <div className="h-20 flex items-center px-8 border-b border-border">
          <h1 className="text-xl font-bold tracking-tighter text-gradient-accent">
            ZOE<span className="text-text-muted" style={{ WebkitTextFillColor: 'var(--color-text-muted)' }}>_</span>TERMINAL
          </h1>
        </div>

        <nav className="p-4 space-y-2 pb-36 overflow-y-auto max-h-[calc(100vh-180px)]">
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
                    ? "bg-surface-highlight text-text-primary shadow-soft border-l-[3px] border-l-text-primary/30"
                    : "text-text-secondary hover:text-text-primary hover:bg-text-primary/[0.03] border-l-[3px] border-l-transparent"
                )}
              >
                <Icon className={cn("w-4 h-4", isActive ? "text-profit" : "")} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-6 left-6 right-6 space-y-3">
          <div className="bg-surface-base/50 p-3 rounded-cards border border-border flex flex-col gap-1">
             <div className="text-[10px] uppercase tracking-widest text-text-muted font-medium">Node Instance</div>
             <div className="text-xs font-mono text-text-primary truncate opacity-80">primary-v4</div>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-btns text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-loss hover:bg-loss/5 border border-border hover:border-loss/20 transition-all"
          >
            <LogOut className="w-3.5 h-3.5" />
            Log Out
          </button>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-[65] lg:hidden backdrop-blur-md"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}
