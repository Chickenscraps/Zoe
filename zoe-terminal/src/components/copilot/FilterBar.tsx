import { cn } from '../../lib/utils';
import { SOURCE_CONFIG } from '../../lib/copilotTypes';
import type { FeedItem, FeedFilter } from '../../lib/copilotTypes';
import { ChevronDown } from 'lucide-react';

interface FilterBarProps {
  filter: FeedFilter;
  toggleSource: (source: FeedItem['source']) => void;
  updateFilter: (patch: Partial<FeedFilter>) => void;
}

const SOURCE_OPTIONS: { value: 'all' | FeedItem['source']; label: string; color: string }[] = [
  { value: 'all', label: 'Show All', color: 'text-text-primary' },
  { value: 'trade', label: 'Trades', color: SOURCE_CONFIG.trade.color },
  { value: 'system', label: 'System', color: SOURCE_CONFIG.system.color },
  { value: 'thought', label: 'Thoughts', color: SOURCE_CONFIG.thought.color },
  { value: 'config', label: 'Config', color: SOURCE_CONFIG.config.color },
  { value: 'chat', label: 'Chat', color: SOURCE_CONFIG.chat.color },
];

const SEVERITY_OPTIONS: { value: FeedFilter['severity']; label: string }[] = [
  { value: 'all', label: 'Any Severity' },
  { value: 'critical', label: 'Critical' },
  { value: 'warning', label: 'Warning' },
  { value: 'success', label: 'Success' },
  { value: 'info', label: 'Info' },
];

export default function FilterBar({ filter, updateFilter }: FilterBarProps) {
  // Determine current source selection for the dropdown
  const allSourcesActive = filter.sources.size === 5; // all 5 source types enabled
  const activeSources = Array.from(filter.sources);
  const currentSourceValue: string = allSourcesActive ? 'all' : (activeSources.length === 1 ? activeSources[0] : 'all');

  const handleSourceChange = (value: string) => {
    if (value === 'all') {
      // Enable all sources
      updateFilter({ sources: new Set(['chat', 'thought', 'system', 'trade', 'config']) });
    } else {
      // Show only the selected source
      updateFilter({ sources: new Set([value as FeedItem['source']]) });
    }
  };

  return (
    <div className="px-3 py-2 border-b border-border flex items-center gap-2">
      {/* Source dropdown */}
      <div className="relative flex-1">
        <select
          value={currentSourceValue}
          onChange={e => handleSourceChange(e.target.value)}
          className={cn(
            "w-full appearance-none bg-surface-base border border-border rounded-[4px] px-3 py-1.5 pr-7",
            "text-[10px] font-black uppercase tracking-widest text-text-primary",
            "focus:outline-none focus:border-border-strong cursor-pointer",
          )}
        >
          {SOURCE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-text-muted pointer-events-none" />
      </div>

      {/* Severity dropdown */}
      <div className="relative">
        <select
          value={filter.severity}
          onChange={e => updateFilter({ severity: e.target.value as FeedFilter['severity'] })}
          className={cn(
            "appearance-none bg-surface-base border border-border rounded-[4px] px-3 py-1.5 pr-7",
            "text-[10px] font-black uppercase tracking-widest text-text-primary",
            "focus:outline-none focus:border-border-strong cursor-pointer",
          )}
        >
          {SEVERITY_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-text-muted pointer-events-none" />
      </div>

      {/* Symbol quick-filter */}
      <input
        type="text"
        placeholder="Symbol..."
        value={filter.symbol}
        onChange={e => updateFilter({ symbol: e.target.value.toUpperCase() })}
        className="w-20 bg-surface-base border border-border rounded-[4px] px-2 py-1.5 text-[10px] font-bold text-text-primary placeholder:text-text-dim focus:outline-none focus:border-border-strong"
      />
    </div>
  );
}
