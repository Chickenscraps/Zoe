import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

export type CopilotTab = 'feed' | 'dials' | 'actions';

interface CopilotContextType {
  isOpen: boolean;
  toggle: () => void;
  setOpen: (open: boolean) => void;
  activeTab: CopilotTab;
  setActiveTab: (tab: CopilotTab) => void;
}

const CopilotContext = createContext<CopilotContextType | null>(null);

export function CopilotProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(() => {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem('zoe_copilot_open') === 'true';
    }
    return false;
  });
  const [activeTab, setActiveTab] = useState<CopilotTab>('feed');
  const location = useLocation();

  const toggle = useCallback(() => {
    setIsOpen(prev => {
      const next = !prev;
      localStorage.setItem('zoe_copilot_open', String(next));
      return next;
    });
  }, []);

  const setOpen = useCallback((open: boolean) => {
    setIsOpen(open);
    localStorage.setItem('zoe_copilot_open', String(open));
  }, []);

  // Auto-close on mobile route change
  useEffect(() => {
    if (window.innerWidth < 1024) {
      setIsOpen(false);
    }
  }, [location.pathname]);

  // Keyboard shortcut: Ctrl+K / Cmd+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggle]);

  return (
    <CopilotContext.Provider value={{ isOpen, toggle, setOpen, activeTab, setActiveTab }}>
      {children}
    </CopilotContext.Provider>
  );
}

export function useCopilotContext() {
  const ctx = useContext(CopilotContext);
  if (!ctx) throw new Error('useCopilotContext must be used within CopilotProvider');
  return ctx;
}
