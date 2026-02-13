import { createContext, useContext, useState, useLayoutEffect, useCallback, type ReactNode } from 'react';

export type TradingMode = 'paper' | 'live';

interface ModeContextType {
  mode: TradingMode;
  setMode: (mode: TradingMode) => void;
  isPaper: boolean;
  isLive: boolean;
}

const ModeContext = createContext<ModeContextType | null>(null);

function getInitialMode(): TradingMode {
  // Priority: URL param > localStorage > env var > default
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const urlMode = params.get('mode');
    if (urlMode === 'paper' || urlMode === 'live') return urlMode;

    const stored = localStorage.getItem('zoe_mode');
    if (stored === 'paper' || stored === 'live') return stored;
  }

  // Fall back to build-time env var if set (backward compat)
  const envMode = import.meta.env.VITE_MODE_LOCK;
  if (envMode === 'paper') return 'paper';

  return 'live';
}

// Apply theme attribute synchronously to prevent flash
const initialMode = getInitialMode();
if (typeof document !== 'undefined') {
  document.documentElement.setAttribute('data-theme', initialMode === 'paper' ? 'paper' : 'dark');
}

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<TradingMode>(initialMode);

  useLayoutEffect(() => {
    document.documentElement.setAttribute('data-theme', mode === 'paper' ? 'paper' : 'dark');
    localStorage.setItem('zoe_mode', mode);
  }, [mode]);

  const setMode = useCallback((newMode: TradingMode) => {
    setModeState(newMode);
    // Update URL without full navigation
    const url = new URL(window.location.href);
    url.searchParams.set('mode', newMode);
    window.history.replaceState({}, '', url.toString());
  }, []);

  return (
    <ModeContext.Provider value={{
      mode,
      setMode,
      isPaper: mode === 'paper',
      isLive: mode === 'live',
    }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useModeContext(): ModeContextType {
  const ctx = useContext(ModeContext);
  if (!ctx) throw new Error('useModeContext must be used within ModeProvider');
  return ctx;
}
