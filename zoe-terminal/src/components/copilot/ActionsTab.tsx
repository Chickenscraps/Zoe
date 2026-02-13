import { useState } from 'react';
import { Scan, Trash2, HeartPulse, RotateCcw, Loader2, Check, AlertCircle, Lock } from 'lucide-react';
import { useAuth } from '../../lib/AuthContext';
import { cn } from '../../lib/utils';

interface ActionDef {
  id: string;
  label: string;
  description: string;
  icon: typeof Scan;
  endpoint: string;
  destructive?: boolean;
}

const ACTIONS: ActionDef[] = [
  { id: 'force_scan', label: 'Force Scan', description: 'Trigger an immediate market scan', icon: Scan, endpoint: '/api/actions/force_scan' },
  { id: 'health_check', label: 'Health Check', description: 'Run system health diagnostics', icon: HeartPulse, endpoint: '/api/health' },
  { id: 'clear_cache', label: 'Clear Cache', description: 'Clear local browser cache', icon: Trash2, endpoint: '', destructive: true },
  { id: 'restart_scanner', label: 'Restart Scanner', description: 'Restart the scanner process', icon: RotateCcw, endpoint: '/api/actions/restart_scanner', destructive: true },
];

export default function ActionsTab() {
  const { isGuest } = useAuth();
  const [states, setStates] = useState<Record<string, 'idle' | 'loading' | 'success' | 'error'>>({});

  const executeAction = async (action: ActionDef) => {
    setStates(prev => ({ ...prev, [action.id]: 'loading' }));

    try {
      if (action.id === 'clear_cache') {
        localStorage.clear();
        sessionStorage.clear();
      } else {
        const res = await fetch(action.endpoint, { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
      }
      setStates(prev => ({ ...prev, [action.id]: 'success' }));
      setTimeout(() => setStates(prev => ({ ...prev, [action.id]: 'idle' })), 2000);
    } catch {
      setStates(prev => ({ ...prev, [action.id]: 'error' }));
      setTimeout(() => setStates(prev => ({ ...prev, [action.id]: 'idle' })), 3000);
    }
  };

  return (
    <div className="p-3 space-y-2">
      {isGuest && (
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-800/10 border border-amber-800/15 rounded-lg text-[10px] font-bold text-amber-500/70 uppercase tracking-wider">
          <Lock className="w-3 h-3" /> View Only — Guest Access
        </div>
      )}
      {ACTIONS.map(action => {
        const state = states[action.id] ?? 'idle';
        const Icon = action.icon;

        return (
          <button
            key={action.id}
            onClick={() => !isGuest && executeAction(action)}
            disabled={state === 'loading' || isGuest}
            className={cn(
              "w-full text-left bg-surface-base border border-border rounded-lg p-3 transition-all hover:border-border-strong",
              action.destructive && "hover:border-loss/30",
              state === 'success' && "border-profit/30",
              state === 'error' && "border-loss/30",
            )}
          >
            <div className="flex items-center gap-3">
              <div className={cn(
                "p-1.5 rounded",
                action.destructive ? "bg-loss/10 text-loss" : "bg-surface-highlight text-text-secondary",
              )}>
                {state === 'loading' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : state === 'success' ? (
                  <Check className="w-4 h-4 text-profit" />
                ) : state === 'error' ? (
                  <AlertCircle className="w-4 h-4 text-loss" />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
              </div>
              <div>
                <div className="text-[11px] font-bold text-white">{action.label}</div>
                <div className="text-[9px] text-text-dim">{action.description}</div>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
