import { createContext, useContext, type ReactNode } from 'react';

export type TradingMode = 'live';

interface ModeContextType {
  mode: TradingMode;
  isLive: boolean;
}

const ModeContext = createContext<ModeContextType | null>(null);

// Always dark theme
if (typeof document !== 'undefined') {
  document.documentElement.setAttribute('data-theme', 'dark');
}

export function ModeProvider({ children }: { children: ReactNode }) {
  return (
    <ModeContext.Provider value={{ mode: 'live', isLive: true }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useModeContext(): ModeContextType {
  const ctx = useContext(ModeContext);
  if (!ctx) throw new Error('useModeContext must be used within ModeProvider');
  return ctx;
}
