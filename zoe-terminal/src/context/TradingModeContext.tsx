import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

type TradingMode = 'PAPER' | 'LIVE';

interface TradingModeContextType {
  mode: TradingMode;
  setMode: (mode: TradingMode) => void;
  isLive: boolean;
}

const TradingModeContext = createContext<TradingModeContextType | undefined>(undefined);

export function TradingModeProvider({ children }: { children: ReactNode }) {
  // Default to PAPER for safety
  const [mode, setModeState] = useState<TradingMode>('PAPER');

  // Load initial mode from API or Env (Mock for now)
  useEffect(() => {
    // In real app, fetch from /api/status
    // fetch('/api/status').then(res => res.json()).then(data => setModeState(data.mode));
    console.log("Trading Mode initialized:", mode);
    
    // Apply theme class to body
    document.body.classList.remove('theme-paper', 'theme-live');
    document.body.classList.add(`theme-${mode.toLowerCase()}`);
    
  }, [mode]);

  const setMode = (newMode: TradingMode) => {
    if (newMode === 'LIVE') {
        const confirm = window.prompt("TYPE 'LIVE' TO CONFIRM REAL MONEY TRADING:");
        if (confirm !== 'LIVE') return;
    }
    setModeState(newMode);
  };

  return (
    <TradingModeContext.Provider value={{ mode, setMode, isLive: mode === 'LIVE' }}>
      {children}
    </TradingModeContext.Provider>
  );
}

export function useTradingMode() {
  const context = useContext(TradingModeContext);
  if (context === undefined) {
    throw new Error('useTradingMode must be used within a TradingModeProvider');
  }
  return context;
}
