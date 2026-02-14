import { lazy, Suspense } from 'react';
import { X } from 'lucide-react';
import { cn } from '../lib/utils';
import { useCopilotContext, type CopilotTab } from '../lib/CopilotContext';
import { useAutoNudge } from '../hooks/useAutoNudge';

const FeedTab = lazy(() => import('./copilot/FeedTab'));
const DialsTab = lazy(() => import('./copilot/DialsTab'));
const ActionsTab = lazy(() => import('./copilot/ActionsTab'));

const TABS: { id: CopilotTab; label: string }[] = [
  { id: 'feed', label: 'Feed' },
  { id: 'dials', label: 'Dials' },
  { id: 'actions', label: 'Actions' },
];

export default function CopilotSidebar() {
  const { isOpen, setOpen, activeTab, setActiveTab } = useCopilotContext();

  // Auto-nudge: periodically injects system events into the feed
  useAutoNudge();

  return (
    <>
      {/* Mobile backdrop — only shown when open on mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-[65] lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar panel — fixed at root level, always above content */}
      <aside className={cn(
        "fixed right-0 top-0 bottom-0 z-[70] w-80 bg-paper-100 border-l border-border flex flex-col transition-transform duration-200 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}>
        {/* Header */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-border">
          <h2 className="font-pixel text-[0.5rem] uppercase tracking-[0.08em] text-text-primary">
            ZOE<span className="text-text-muted">_</span>COPILOT
          </h2>
          <button
            onClick={() => setOpen(false)}
            className="p-1 text-text-muted hover:text-text-primary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-border">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex-1 py-2 text-[10px] font-black uppercase tracking-[0.15em] transition-all relative",
                activeTab === tab.id
                  ? "text-text-primary"
                  : "text-text-muted hover:text-text-secondary",
              )}
            >
              {tab.label}
              {activeTab === tab.id && (
                <div className="absolute bottom-0 inset-x-4 h-[2px] bg-text-primary rounded-full" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden min-h-0">
          <Suspense fallback={<div className="p-4 text-text-muted text-xs animate-pulse">Loading...</div>}>
            {activeTab === 'feed' && <FeedTab />}
            {activeTab === 'dials' && <DialsTab />}
            {activeTab === 'actions' && <ActionsTab />}
          </Suspense>
        </div>
      </aside>
    </>
  );
}
