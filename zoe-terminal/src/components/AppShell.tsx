import { useState, lazy, Suspense } from 'react';
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
import SnesNav from './snes/SnesNav';
import SakuraPetals from './snes/SakuraPetals';
import SnesButton from './snes/SnesButton';

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
  const { isGuest, logout } = useAuth();
  const { isOpen: copilotOpen, toggle: toggleCopilot } = useCopilotContext();
  const systemHealth = useSystemHealth();

  return (
    <div className="h-screen bg-background text-text-primary flex flex-col relative">
      {/* Background layers */}
      <SakuraPetals />

      {/* Guest Banner */}
      {isGuest && (
        <div className="w-full text-center py-1 font-pixel text-[0.35rem] tracking-[0.2em] uppercase z-[60] relative select-none bg-earth-700/8 text-earth-700/60 border-b border-earth-700/10">
          VIEW ONLY — Guest Access
        </div>
      )}

      {/* Circuit Breaker Banner */}
      <CircuitBreakerBanner health={systemHealth} />

      <div className="flex flex-1 relative overflow-hidden">
      {/* Desktop sidebar spacer */}
      <div className="hidden lg:block w-56 shrink-0" />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 sm:h-16 border-b border-earth-700/10 bg-cream-100/60 backdrop-blur-xl sticky top-0 z-30 flex items-center justify-between px-3 sm:px-8">
          <div className="flex items-center gap-2">
            <button
              className="lg:hidden p-2 -ml-1 text-earth-700/60 hover:text-earth-700 transition-colors z-[75] relative"
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
                   "p-1.5 sm:p-2 rounded-[4px] border-2 transition-all",
                   copilotOpen
                     ? "bg-sakura-500/15 text-sakura-700 border-sakura-500/30"
                     : "bg-cream-100/50 text-text-muted border-earth-700/10 hover:text-earth-700 hover:border-earth-700/20"
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
            <div className="border-t border-earth-700/10 pt-6">
              <p className="font-pixel text-[0.35rem] text-text-dim tracking-wider uppercase">
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
          "fixed inset-y-0 left-0 z-[70] w-56 bg-paper-100/95 backdrop-blur-md border-r border-earth-700/10 transform transition-transform duration-200 ease-in-out",
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        <div className="h-16 flex items-center px-5 border-b border-earth-700/10">
          <h1 className="font-pixel text-[0.5rem] uppercase tracking-[0.08em] text-gradient-accent">
            ZOE Terminal
          </h1>
        </div>

        <div className="pb-36 overflow-y-auto max-h-[calc(100vh-180px)]">
          <SnesNav items={NAV_ITEMS} />
        </div>

        <div className="absolute bottom-6 left-4 right-4 space-y-3">
          <div className="bg-cream-100/60 p-3 rounded-[4px] border-2 border-earth-700/10 flex flex-col gap-1">
             <div className="font-pixel text-[0.3rem] uppercase tracking-widest text-text-muted">Node Instance</div>
             <div className="text-[10px] font-mono text-text-primary truncate opacity-80">primary-v4</div>
          </div>
          <SnesButton
            variant="secondary"
            size="sm"
            onClick={logout}
            className="w-full flex items-center justify-center gap-2"
          >
            <LogOut className="w-3 h-3" />
            Log Out
          </SnesButton>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-night-900/40 z-[65] lg:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}
