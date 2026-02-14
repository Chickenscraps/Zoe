import { useState, useEffect, useMemo } from 'react';
import { useDials } from '../../hooks/useDials';
import { useAuth } from '../../lib/AuthContext';
import { cn } from '../../lib/utils';
import { supabase } from '../../lib/supabaseClient';
import { Loader2, Zap, Shield, Target, TrendingUp, Pause, Lock, RotateCcw, Check, Wand2 } from 'lucide-react';

interface Preset {
  name: string;
  description: string;
  icon: typeof Zap;
  color: string;
  values: Record<string, unknown>;
}

const PRESETS: Preset[] = [
  {
    name: 'Conservative',
    description: 'Low risk, tight stops, fewer trades. Best for choppy or uncertain markets.',
    icon: Shield,
    color: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
    values: {
      kill_switch: false,
      scan_interval_s: 300,
      min_score: 75,
      max_pct_per_trade: 2,
      stop_loss_pct: 2,
    },
  },
  {
    name: 'Balanced',
    description: 'Moderate risk/reward. Default settings for normal market conditions.',
    icon: Target,
    color: 'text-profit bg-profit/10 border-profit/20',
    values: {
      kill_switch: false,
      scan_interval_s: 120,
      min_score: 50,
      max_pct_per_trade: 5,
      stop_loss_pct: 3,
    },
  },
  {
    name: 'Aggressive',
    description: 'Higher allocations, wider stops, faster scans. For high-conviction trending markets.',
    icon: TrendingUp,
    color: 'text-orange-400 bg-orange-400/10 border-orange-400/20',
    values: {
      kill_switch: false,
      scan_interval_s: 60,
      min_score: 30,
      max_pct_per_trade: 15,
      stop_loss_pct: 5,
    },
  },
  {
    name: 'Scalper',
    description: 'Rapid-fire micro trades. Tight stops, fast scans, low score threshold.',
    icon: Zap,
    color: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    values: {
      kill_switch: false,
      scan_interval_s: 15,
      min_score: 20,
      max_pct_per_trade: 3,
      stop_loss_pct: 1.5,
    },
  },
  {
    name: 'Paused',
    description: 'Emergency pause ON. All automation halted.',
    icon: Pause,
    color: 'text-loss bg-loss/10 border-loss/20',
    values: {
      kill_switch: true,
      scan_interval_s: 300,
      min_score: 50,
      max_pct_per_trade: 5,
      stop_loss_pct: 3,
    },
  },
];

/** Compare dial keys (ignoring kill_switch for closest-match) */
const DIAL_KEYS = ['scan_interval_s', 'min_score', 'max_pct_per_trade', 'stop_loss_pct'];

function findClosestPreset(values: Record<string, unknown>): { exact: Preset | null; closest: Preset } {
  let bestDist = Infinity;
  let closest = PRESETS[1]; // Balanced default
  let exact: Preset | null = null;

  for (const preset of PRESETS) {
    let dist = 0;
    let isExact = true;
    for (const key of DIAL_KEYS) {
      const pVal = Number(preset.values[key] ?? 0);
      const cVal = Number(values[key] ?? 0);
      if (pVal !== cVal) isExact = false;
      // Normalized distance (% difference)
      const range = key === 'scan_interval_s' ? 285 : key === 'min_score' ? 100 : key === 'max_pct_per_trade' ? 99 : 9.5;
      dist += Math.abs(pVal - cVal) / range;
    }
    // Also check kill_switch for exact match
    if (preset.values.kill_switch !== values.kill_switch) isExact = false;
    if (isExact) exact = preset;
    if (dist < bestDist) {
      bestDist = dist;
      closest = preset;
    }
  }

  return { exact, closest };
}

export default function DialsTab() {
  const { dials, values, loading, applying, hasChanges, setValue, applyChanges, discardChanges } = useDials();
  const { isGuest } = useAuth();
  const [applyingPreset, setApplyingPreset] = useState<string | null>(null);
  const [autoAdjust, setAutoAdjust] = useState(false);
  const [currentRegime, setCurrentRegime] = useState<string | null>(null);
  const [togglingAuto, setTogglingAuto] = useState(false);

  // Load auto_adjust + current_regime from config
  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from('config')
        .select('key, value')
        .in('key', ['auto_adjust', 'current_regime']);
      if (data) {
        for (const row of data) {
          if (row.key === 'auto_adjust') setAutoAdjust(!!row.value);
          if (row.key === 'current_regime') setCurrentRegime(row.value as string);
        }
      }
    }
    load();
  }, []);

  const toggleAutoAdjust = async () => {
    if (isGuest) return;
    setTogglingAuto(true);
    const newVal = !autoAdjust;
    try {
      await supabase.from('config').upsert({ key: 'auto_adjust', value: newVal });
      await supabase.from('audit_log').insert({
        event_type: 'config_change',
        details: `Auto-adjust ${newVal ? 'enabled' : 'disabled'}`,
        metadata: { key: 'auto_adjust', value: newVal, source: 'copilot_dials' },
      });
      setAutoAdjust(newVal);
    } catch (err) {
      console.error('Failed to toggle auto_adjust:', err);
    } finally {
      setTogglingAuto(false);
    }
  };

  // Determine which preset is active/closest
  const { exact: activePreset, closest: closestPreset } = useMemo(() => findClosestPreset(values), [values]);
  const displayPreset = activePreset || closestPreset;

  const applyPreset = (preset: Preset) => {
    setApplyingPreset(preset.name);
    for (const [key, val] of Object.entries(preset.values)) {
      setValue(key, val);
    }
    // Brief visual feedback
    setTimeout(() => setApplyingPreset(null), 400);
  };

  if (loading) {
    return <div className="p-4 text-text-muted text-xs animate-pulse">Loading dials...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 space-y-4 overflow-y-auto flex-1 min-h-0">
        {isGuest && (
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-800/10 border border-amber-800/15 rounded-lg text-[10px] font-bold text-amber-500/70 uppercase tracking-wider">
            <Lock className="w-3 h-3" /> View Only — Guest Access
          </div>
        )}

        {/* Active Preset / Regime Banner */}
        <div className={cn(
          "px-3 py-2 rounded-lg border",
          displayPreset?.color ?? 'text-text-muted bg-surface-base border-border',
        )}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {displayPreset && (() => { const Icon = displayPreset.icon; return <Icon className="w-3.5 h-3.5" />; })()}
              <span className="text-[10px] font-black uppercase tracking-widest">
                {activePreset ? activePreset.name : `~${closestPreset.name}`}
              </span>
              {!activePreset && (
                <span className="text-[8px] opacity-50 font-normal">(custom)</span>
              )}
            </div>
            {currentRegime && (
              <span className="text-[9px] opacity-70 font-bold uppercase">
                {currentRegime} market
              </span>
            )}
          </div>
        </div>

        {/* Auto-Adjust Toggle */}
        <div className="bg-surface-base border border-border rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <Wand2 className="w-3.5 h-3.5 text-purple-400" />
              <span className="text-[11px] font-bold text-white">Auto-Adjust</span>
            </div>
            <button
              role="switch"
              aria-checked={autoAdjust}
              aria-label="Auto-Adjust"
              disabled={isGuest || togglingAuto}
              onClick={toggleAutoAdjust}
              className={cn(
                "w-10 h-5 rounded-full transition-colors relative",
                autoAdjust ? "bg-purple-500" : "bg-surface-highlight",
              )}
            >
              <div
                className={cn(
                  "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform",
                  autoAdjust ? "translate-x-5" : "translate-x-0.5",
                )}
              />
            </button>
          </div>
          <p className="text-[9px] text-text-dim">
            Bot auto-switches presets based on market regime (bull/bear/sideways/high vol)
          </p>
        </div>

        {/* Presets Section */}
        <div>
          <div className="text-[9px] font-black uppercase tracking-[0.2em] text-text-muted mb-2 px-1">Presets</div>
          <div className="space-y-1.5">
            {PRESETS.map(preset => {
              const Icon = preset.icon;
              const isApplying = applyingPreset === preset.name;
              const isActive = activePreset?.name === preset.name;
              return (
                <button
                  key={preset.name}
                  onClick={() => !isGuest && applyPreset(preset)}
                  disabled={!!applyingPreset || isGuest}
                  className={cn(
                    "w-full text-left px-3 py-2.5 rounded-lg border transition-all",
                    "hover:scale-[0.99] active:scale-[0.98]",
                    preset.color,
                    isApplying && "ring-1 ring-white/20",
                    isActive && "ring-1 ring-white/30",
                  )}
                >
                  <div className="flex items-center gap-2 mb-0.5">
                    {isApplying ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Icon className="w-3.5 h-3.5" />
                    )}
                    <span className="text-[11px] font-bold">{preset.name}</span>
                    {isActive && (
                      <span className="ml-auto text-[8px] opacity-60 font-bold uppercase tracking-wider">Active</span>
                    )}
                  </div>
                  <p className="text-[9px] opacity-70 leading-tight">{preset.description}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-border" />

        {/* Individual Dials */}
        <div>
          <div className="text-[9px] font-black uppercase tracking-[0.2em] text-text-muted mb-2 px-1">Fine Tune</div>
          {dials.map(dial => {
            const currentValue = values[dial.key];

            return (
              <div key={dial.key} className="bg-surface-base border border-border rounded-lg p-3 mb-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-bold text-white">{dial.label}</span>
                </div>
                <p className="text-[9px] text-text-dim mb-2">{dial.description}</p>

                {dial.type === 'boolean' ? (
                  <button
                    role="switch"
                    aria-checked={!!currentValue}
                    aria-label={dial.label}
                    disabled={isGuest}
                    onClick={() => !isGuest && setValue(dial.key, !currentValue)}
                    className={cn(
                      "w-10 h-5 rounded-full transition-colors relative",
                      currentValue ? "bg-profit" : "bg-surface-highlight",
                    )}
                  >
                    <div
                      className={cn(
                        "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform",
                        currentValue ? "translate-x-5" : "translate-x-0.5",
                      )}
                    />
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min={dial.min}
                      max={dial.max}
                      step={dial.step}
                      value={Number(currentValue ?? dial.min ?? 0)}
                      onChange={e => !isGuest && setValue(dial.key, Number(e.target.value))}
                      disabled={isGuest}
                      aria-label={dial.label}
                      className="flex-1 accent-profit h-1"
                    />
                    <span className="text-[10px] font-mono text-text-secondary tabular-nums w-10 text-right">
                      {Number(currentValue ?? dial.min ?? 0)}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Sticky Apply / Discard Bar — only visible when changes exist */}
      {hasChanges && !isGuest && (
        <div className="border-t border-border bg-surface/95 backdrop-blur-sm px-3 py-3 flex items-center gap-2 shrink-0">
          <button
            onClick={applyChanges}
            disabled={applying}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all border",
              "bg-profit/15 text-profit border-profit/30 hover:bg-profit/25",
              applying && "opacity-60 cursor-wait",
            )}
          >
            {applying ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Check className="w-3.5 h-3.5" />
            )}
            {applying ? 'Applying...' : 'Apply Changes'}
          </button>
          <button
            onClick={discardChanges}
            disabled={applying}
            className="p-2.5 rounded-lg text-text-muted hover:text-loss border border-border hover:border-loss/20 transition-all"
            title="Discard changes"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
