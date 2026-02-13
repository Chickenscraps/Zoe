import { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
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
  Power,
  LogOut,
  Bot,
} from 'lucide-react';
import { cn, formatCurrency } from '../lib/utils';
import { useDashboardData } from '../hooks/useDashboardData';
import { useModeContext } from '../lib/mode';
import { useAuth } from '../lib/AuthContext';
import { useCopilotContext } from '../lib/CopilotContext';
import { ErrorBoundary } from './ErrorBoundary';
import { supabase } from '../lib/supabaseClient';

const Starfield = lazy(() => import('./Starfield'));
const CopilotSidebar = lazy(() => import('./CopilotSidebar'));

const NAV_ITEMS = [
  { label: 'Overview', path: '/', icon: LayoutDashboard },
  { label: 'Trades', path: '/trades', icon: History },
  { label: 'Scanner', path: '/scanner', icon: Scan },
  { label: 'Charts', path: '/charts', icon: BarChart3 },
  { label: 'Intelligence', path: '/intelligence', icon: BrainCircuit },
  { label: 'Settings', path: '/settings', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [tradingActive, setTradingActive] = useState(false);
  const [tradingToggling, setTradingToggling] = useState(false);
  const [killConfirmOpen, setKillConfirmOpen] = useState(false);
  const location = useLocation();
  const { cryptoCash, accountOverview, holdingsRows, livePrices, initialDeposit } = useDashboardData();
  const { mode, setMode, isPaper, isLive } = useModeContext();
  const { isGuest, logout } = useAuth();
  const { isOpen: copilotOpen, toggle: toggleCopilot } = useCopilotContext();

  // Compute total portfolio value (cash + crypto)
  const cashValue = cryptoCash?.buying_power ?? cryptoCash?.cash_available ?? accountOverview?.equity ?? 0;
  const cryptoValue = useMemo(() => {
    if (!holdingsRows?.length || !livePrices?.length) return 0;
    let total = 0;
    for (const row of holdingsRows) {
      const scan = livePrices.find(s => s.symbol === row.asset);
      const mid = scan ? ((scan.info as any)?.mid ?? 0) : 0;
      total += row.qty * mid;
    }
    return total;
  }, [holdingsRows, livePrices]);
  const totalValue = cashValue + cryptoValue;

  // All-time P&L: total value (cash + crypto) - initial deposit
  const totalPnl = initialDeposit > 0 ? totalValue - initialDeposit : 0;
  const totalReturnPct = initialDeposit > 0 ? ((totalValue - initialDeposit) / initialDeposit) * 100 : 0;

  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [currentRegime, setCurrentRegime] = useState<string | null>(null);

  // Load kill_switch + active_preset + current_regime from config table
  useEffect(() => {
    async function loadConfig() {
      const { data } = await supabase
        .from('config')
        .select('key, value')
        .in('key', ['kill_switch', 'active_preset', 'current_regime']);
      if (data) {
        for (const row of data) {
          if (row.key === 'kill_switch') {
            setTradingActive(row.value === false || !row);
          } else if (row.key === 'active_preset') {
            setActivePreset(row.value as string);
          } else if (row.key === 'current_regime') {
            setCurrentRegime(row.value as string);
          }
        }
        // If no kill_switch row, default to active
        if (!data.find(r => r.key === 'kill_switch')) {
          setTradingActive(true);
        }
      }
    }
    loadConfig();
    // Poll every 30s to stay in sync
    const interval = setInterval(loadConfig, 30_000);
    return () => clearInterval(interval);
  }, [mode]);

  /** Actually perform the toggle (called after confirmation if turning OFF) */
  const doToggle = useCallback(async () => {
    const newActive = !tradingActive;
    setTradingToggling(true);
    setKillConfirmOpen(false);
    try {
      setTradingActive(newActive);
      await supabase.from('config').upsert({
        key: 'kill_switch',
        value: !newActive,
      });
      await supabase.from('audit_log').insert({
        event_type: 'trading_toggle',
        message: `Trading ${newActive ? 'activated' : 'paused'} (mode=${mode})`,
        metadata: { kill_switch: !newActive, mode, source: 'dashboard_header' },
      });
    } catch (err) {
      console.error('Failed to toggle trading:', err);
      setTradingActive(!newActive);
    } finally {
      setTradingToggling(false);
    }
  }, [tradingActive, mode]);

  /** Toggle with confirmation when turning OFF */
  const handleToggleTrading = useCallback(() => {
    if (tradingActive) {
      // Turning OFF — require confirmation
      setKillConfirmOpen(true);
    } else {
      // Turning ON — no confirmation needed
      doToggle();
    }
  }, [tradingActive, doToggle]);

  const closeSidebar = () => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  return (
    <div className={cn("h-screen bg-background text-text-primary flex flex-col relative", tradingActive && "trading-active-border")}>
      {isLive && (
        <Suspense fallback={null}>
          <Starfield />
        </Suspense>
      )}
      <div className="noise-overlay" style={{ zIndex: 2 }} />

      {/* Mode Banner */}
      <div className={cn(
        "w-full text-center py-1.5 text-[11px] font-black tracking-[0.25em] uppercase z-[60] relative select-none",
        isPaper
          ? "bg-profit/15 text-profit border-b border-profit/20"
          : "bg-loss/15 text-loss border-b border-loss/20 animate-pulse"
      )}>
        {isPaper ? "◆ PAPER TRADING ◆" : "◆ LIVE TRADING ◆"}
      </div>

      {/* Guest Banner */}
      {isGuest && (
        <div className="w-full text-center py-1 text-[10px] font-bold tracking-[0.2em] uppercase z-[60] relative select-none bg-amber-800/10 text-amber-500/70 border-b border-amber-800/15">
          VIEW ONLY — Guest Access
        </div>
      )}

      <div className="flex flex-1 relative overflow-hidden">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-[70] w-64 bg-surface border-r border-border transform transition-transform duration-200 ease-in-out lg:relative lg:z-auto lg:translate-x-0 shadow-crisp",
          !sidebarOpen && "-translate-x-full"
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
             <div className="text-xs font-mono text-text-primary truncate opacity-80">primary-v4-live</div>
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
            {/* Kill Switch — top left with confirmation */}
            <button
              onClick={isGuest ? undefined : handleToggleTrading}
              disabled={tradingToggling || isGuest}
              className={cn(
                "flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1.5 rounded-full text-[9px] sm:text-[10px] font-black tracking-widest uppercase transition-all border",
                isGuest
                  ? "bg-white/5 text-text-dim border-border cursor-not-allowed opacity-50"
                  : tradingActive
                    ? "bg-profit/15 text-profit border-profit/30 hover:bg-profit/25"
                    : "bg-loss/15 text-loss border-loss/30 hover:bg-loss/25"
              )}
              title={isGuest ? "View only — guest access" : tradingActive ? "Trading is active — click to kill" : "Trading is paused — click to activate"}
            >
              <Power className={cn("w-3.5 h-3.5", isGuest ? "text-text-dim" : tradingActive ? "text-profit" : "text-loss")} />
              <span className="hidden sm:inline">{tradingActive ? "ACTIVE" : "KILLED"}</span>
            </button>
            {/* Active Preset / Regime indicator */}
            {activePreset && tradingActive && (
              <div className={cn(
                "hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-[9px] font-bold tracking-wider uppercase border",
                activePreset === 'Aggressive' ? "bg-orange-400/10 text-orange-400 border-orange-400/20"
                  : activePreset === 'Conservative' ? "bg-blue-400/10 text-blue-400 border-blue-400/20"
                  : activePreset === 'Scalper' ? "bg-yellow-400/10 text-yellow-400 border-yellow-400/20"
                  : "bg-profit/10 text-profit border-profit/20"
              )}>
                {activePreset}
                {currentRegime && (
                  <span className="text-[8px] opacity-60 font-normal">
                    ({currentRegime})
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 sm:gap-6 ml-auto min-w-0">
            <div className="flex items-center gap-2 sm:gap-6 text-sm flex-wrap justify-end">
               <div className="flex flex-col items-end min-w-0">
                 <span className="text-[9px] sm:text-[10px] text-text-muted uppercase font-bold tracking-widest leading-tight">Total P&L</span>
                 <div className="flex items-baseline gap-1.5">
                   <span className={cn("font-mono text-sm sm:text-lg font-black truncate", totalPnl >= 0 ? "text-profit" : "text-loss")}>
                     {totalPnl >= 0 ? '+' : ''}{formatCurrency(totalPnl)}
                   </span>
                   {initialDeposit > 0 && (
                     <span className={cn("text-[9px] sm:text-[10px] font-bold tabular-nums", totalReturnPct >= 0 ? "text-profit/70" : "text-loss/70")}>
                       {totalReturnPct >= 0 ? '+' : ''}{totalReturnPct.toFixed(2)}%
                     </span>
                   )}
                 </div>
               </div>
               <div className="h-8 w-px bg-border hidden sm:block" />
               {/* Mode Toggle */}
               <div className="flex items-center gap-0 bg-surface-base border border-border rounded-full p-0.5">
                 <button
                   onClick={() => setMode('paper')}
                   className={cn(
                     "px-2 sm:px-3 py-1 rounded-full text-[9px] sm:text-[10px] font-black tracking-widest uppercase transition-all",
                     isPaper
                       ? "bg-profit text-background"
                       : "text-text-muted hover:text-text-primary"
                   )}
                 >
                   Paper
                 </button>
                 <button
                   onClick={() => setMode('live')}
                   className={cn(
                     "px-2 sm:px-3 py-1 rounded-full text-[9px] sm:text-[10px] font-black tracking-widest uppercase transition-all",
                     isLive
                       ? "bg-loss text-background"
                       : "text-text-muted hover:text-text-primary"
                   )}
                 >
                   Live
                 </button>
               </div>
               {/* Kill switch is now in top-left */}
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

      {/* Copilot Sidebar */}
      <Suspense fallback={null}>
        <CopilotSidebar />
      </Suspense>

      </div>

      {/* Mobile Overlay — at root level so it covers banners too */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-[65] lg:hidden backdrop-blur-md"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Kill Switch Confirmation Modal */}
      {killConfirmOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setKillConfirmOpen(false)} />
          <div className="relative bg-surface border border-loss/30 rounded-2xl p-6 max-w-sm mx-4 shadow-2xl">
            <div className="text-center mb-4">
              <div className="w-12 h-12 bg-loss/15 rounded-full flex items-center justify-center mx-auto mb-3">
                <Power className="w-6 h-6 text-loss" />
              </div>
              <h3 className="text-lg font-black text-white tracking-tight">Kill Trading?</h3>
              <p className="text-text-muted text-xs mt-2">
                This will immediately stop all automated trading.
                Open positions will NOT be closed.
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setKillConfirmOpen(false)}
                className="flex-1 px-4 py-2.5 rounded-lg text-sm font-bold text-text-secondary bg-surface-highlight border border-border hover:bg-border transition-all"
              >
                Cancel
              </button>
              <button
                onClick={doToggle}
                disabled={tradingToggling}
                className="flex-1 px-4 py-2.5 rounded-lg text-sm font-black text-white bg-loss hover:bg-loss/80 transition-all uppercase tracking-wider"
              >
                {tradingToggling ? 'Killing...' : 'Kill Trading'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
