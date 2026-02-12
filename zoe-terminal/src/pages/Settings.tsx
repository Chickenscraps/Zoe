import { useState, useCallback } from "react";
import {
  Shield,
  Download,
  Trash2,
  AlertTriangle,
  Save,
  RotateCcw,
  ChevronDown,
  Info,
  Clock,
  Zap,
  Target,
  Activity,
  ToggleLeft,
  ToggleRight,
  Check,
} from "lucide-react";
import { supabase } from "../lib/supabaseClient";
import { MODE, isPaper } from "../lib/mode";
import { useDashboardData } from "../hooks/useDashboardData";
import { useStrategyConfig } from "../hooks/useStrategyConfig";
import { cn } from "../lib/utils";
import type { StrategyConfig } from "../lib/strategy-config";
import {
  DIAL_BOUNDS,
  PRESET_PROFILES,
  HIGH_RISK_DIALS,
  configDiff,
  getConfigValue,
  setConfigValue,
  formatDialValue,
} from "../lib/strategy-config";

// ─── Subcomponents ────────────────────────────────────────────────────────

function DialSlider({
  path,
  config,
  onChange,
  error,
}: {
  path: string;
  config: StrategyConfig;
  onChange: (path: string, value: number) => void;
  error?: string;
}) {
  const bounds = DIAL_BOUNDS[path];
  if (!bounds) return null;

  const rawValue = getConfigValue(config, path) as number | undefined;
  const value = rawValue ?? bounds.min;

  const pct = ((value - bounds.min) / (bounds.max - bounds.min)) * 100;
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-text-secondary">{bounds.label}</label>
          <button
            className="text-text-dim hover:text-text-muted transition-colors"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip(!showTooltip)}
            type="button"
          >
            <Info className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={bounds.format === "percent" ? +(value * 100).toFixed(2) : +value.toFixed(2)}
            onChange={(e) => {
              const parsed = parseFloat(e.target.value);
              if (isNaN(parsed)) return;
              const actual = bounds.format === "percent" ? parsed / 100 : parsed;
              onChange(path, actual);
            }}
            step={bounds.format === "percent" ? +(bounds.step * 100).toFixed(4) : bounds.step}
            className="w-20 bg-surface-base border border-border rounded-btns px-2 py-1 text-sm font-mono text-white text-right focus:border-border-strong focus:outline-none"
          />
          {bounds.unit && (
            <span className="text-xs text-text-dim font-mono w-6">{bounds.unit}</span>
          )}
        </div>
      </div>

      {showTooltip && (
        <div className="text-xs text-text-muted bg-surface-base border border-border rounded-btns px-3 py-2">
          {bounds.tooltip}
        </div>
      )}

      <div className="relative">
        <input
          type="range"
          min={bounds.min}
          max={bounds.max}
          step={bounds.step}
          value={value}
          onChange={(e) => onChange(path, parseFloat(e.target.value))}
          className="w-full h-1.5 bg-surface-highlight rounded-full appearance-none cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white
            [&::-webkit-slider-thumb]:shadow-soft [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-surface-base
            [&::-webkit-slider-thumb]:hover:scale-110 [&::-webkit-slider-thumb]:transition-transform"
          style={{
            background: `linear-gradient(to right, rgba(46,229,157,0.4) 0%, rgba(46,229,157,0.4) ${pct}%, var(--color-surface-highlight) ${pct}%, var(--color-surface-highlight) 100%)`,
          }}
        />
        <div className="flex justify-between mt-1">
          <span className="text-[10px] text-text-dim font-mono">{formatDialValue(path, bounds.min)}</span>
          <span className="text-[10px] text-text-dim font-mono">{formatDialValue(path, bounds.max)}</span>
        </div>
      </div>

      {error && (
        <p className="text-xs text-loss font-medium">{error}</p>
      )}
    </div>
  );
}

function ToggleDial({
  label,
  value,
  onChange,
  tooltip,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
  tooltip?: string;
}) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-text-secondary">{label}</span>
        {tooltip && (
          <button
            className="text-text-dim hover:text-text-muted transition-colors"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            type="button"
          >
            <Info className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <button
        onClick={() => onChange(!value)}
        className={cn(
          "relative w-11 h-6 rounded-full transition-colors duration-200",
          value ? "bg-profit/30 border border-profit/40" : "bg-surface-highlight border border-border"
        )}
        type="button"
      >
        <div
          className={cn(
            "absolute top-0.5 w-5 h-5 rounded-full transition-transform duration-200",
            value ? "translate-x-5 bg-profit" : "translate-x-0.5 bg-text-muted"
          )}
        />
      </button>
      {showTooltip && tooltip && (
        <div className="absolute mt-8 text-xs text-text-muted bg-surface-base border border-border rounded-btns px-3 py-2 max-w-xs z-10">
          {tooltip}
        </div>
      )}
    </div>
  );
}

function DialCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-surface border border-border rounded-cards overflow-hidden">
      <div className="px-6 py-4 border-b border-border bg-surface-highlight/20 flex items-center gap-2">
        <Icon className="w-4 h-4 text-text-muted" />
        <h3 className="font-medium text-sm text-text-primary">{title}</h3>
      </div>
      <div className="px-6 py-5 space-y-5">{children}</div>
    </div>
  );
}

function DiffPreview({
  prev,
  next,
  onConfirm,
  onCancel,
  saving,
  isLive,
}: {
  prev: StrategyConfig | null;
  next: StrategyConfig;
  onConfirm: (reason?: string) => void;
  onCancel: () => void;
  saving: boolean;
  isLive: boolean;
}) {
  const [reason, setReason] = useState("");
  const [liveConfirmText, setLiveConfirmText] = useState("");
  const diff = prev ? configDiff(prev, next) : {};
  const entries = Object.entries(diff);

  const hasHighRisk = entries.some(([key]) => HIGH_RISK_DIALS.has(key));
  const needsLiveConfirm = isLive && hasHighRisk;
  const liveConfirmed = liveConfirmText === "LIVE";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border border-border rounded-cards max-w-lg w-full mx-4 shadow-soft max-h-[80vh] flex flex-col">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <h3 className="font-semibold text-white">Review Changes</h3>
          <span className={cn(
            "text-[10px] font-black tracking-widest uppercase px-2 py-0.5 rounded-full",
            isPaper
              ? "bg-profit/10 text-profit border border-profit/20"
              : "bg-loss/10 text-loss border border-loss/20"
          )}>
            {MODE}
          </span>
        </div>

        <div className="px-6 py-4 overflow-auto flex-1 space-y-3">
          {entries.length === 0 ? (
            <p className="text-text-muted text-sm">No changes detected.</p>
          ) : (
            entries.map(([key, { old: oldVal, new: newVal }]) => (
              <div key={key} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
                <span className="text-xs font-mono text-text-secondary">{key}</span>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-loss">{formatDialValue(key, oldVal)}</span>
                  <span className="text-text-dim">→</span>
                  <span className="text-profit">{formatDialValue(key, newVal)}</span>
                </div>
              </div>
            ))
          )}

          <div className="pt-2">
            <label className="text-xs text-text-muted block mb-1">Reason (optional)</label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Tightening risk after drawdown"
              className="w-full bg-surface-base border border-border rounded-btns px-3 py-2 text-sm text-white placeholder:text-text-dim focus:border-border-strong focus:outline-none"
            />
          </div>

          {needsLiveConfirm && (
            <div className="bg-loss/5 border border-loss/20 rounded-btns p-4 space-y-2">
              <div className="flex items-center gap-2 text-loss text-sm font-bold">
                <AlertTriangle className="w-4 h-4" />
                LIVE Mode — High Risk Change
              </div>
              <p className="text-xs text-text-muted">
                You are changing risk/exposure parameters in LIVE mode. Type <span className="font-mono font-bold text-white">LIVE</span> to confirm.
              </p>
              <input
                type="text"
                value={liveConfirmText}
                onChange={(e) => setLiveConfirmText(e.target.value)}
                placeholder='Type "LIVE" to confirm'
                className="w-full bg-surface-base border border-loss/30 rounded-btns px-3 py-2 text-sm font-mono text-white placeholder:text-text-dim focus:border-loss/50 focus:outline-none"
              />
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-border flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-text-secondary hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason || undefined)}
            disabled={saving || entries.length === 0 || (needsLiveConfirm && !liveConfirmed)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-btns text-sm font-bold transition-all",
              saving || entries.length === 0 || (needsLiveConfirm && !liveConfirmed)
                ? "bg-surface-highlight text-text-dim cursor-not-allowed"
                : "bg-profit/20 text-profit border border-profit/30 hover:bg-profit/30"
            )}
          >
            {saving ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-profit/30 border-t-profit rounded-full animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" />
                Save v{(0) + 1}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Settings Page ──────────────────────────────────────────────────

export default function Settings() {
  const {
    activeConfig,
    draftConfig,
    setDraftConfig,
    auditLog,
    loading,
    saving,
    errors,
    saveError,
    hasChanges,
    saveConfig,
    loadPreset,
    resetDraft,
  } = useStrategyConfig();

  const { cryptoCash, dailyNotional, healthSummary, holdingsRows } = useDashboardData();

  const [showDiffPreview, setShowDiffPreview] = useState(false);
  const [killConfirm, setKillConfirm] = useState(false);
  const [cacheCleared, setCacheCleared] = useState(false);
  const [presetOpen, setPresetOpen] = useState(false);

  const handleDialChange = useCallback(
    (path: string, value: number) => {
      if (!draftConfig) return;
      setDraftConfig(setConfigValue(draftConfig, path, value));
    },
    [draftConfig, setDraftConfig]
  );

  const handleToggle = useCallback(
    (path: string, value: boolean) => {
      if (!draftConfig) return;
      setDraftConfig(setConfigValue(draftConfig, path, value));
    },
    [draftConfig, setDraftConfig]
  );

  const handleSave = useCallback(
    async (reason?: string) => {
      const ok = await saveConfig(reason);
      if (ok) {
        setShowDiffPreview(false);
      }
    },
    [saveConfig]
  );

  const handleExport = () => {
    const exportData = {
      mode: MODE,
      exported_at: new Date().toISOString(),
      active_config: activeConfig,
      audit_log: auditLog,
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `zoe-config-${MODE}-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearCache = () => {
    localStorage.clear();
    sessionStorage.clear();
    setCacheCleared(true);
    setTimeout(() => setCacheCleared(false), 3000);
  };

  const errorMap = Object.fromEntries(errors.map((e) => [e.path, e.message]));

  if (loading || !draftConfig) {
    return (
      <div className="space-y-6 animate-pulse max-w-5xl">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-48 bg-surface border border-border rounded-cards" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl page-enter">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">Trading Dials</h2>
          <p className="text-sm text-text-secondary">
            Strategy configuration &mdash;{" "}
            <span className={isPaper ? "text-profit font-bold" : "text-loss font-bold"}>
              {MODE.toUpperCase()}
            </span>{" "}
            mode
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {/* Preset selector */}
          <div className="relative">
            <button
              onClick={() => setPresetOpen(!presetOpen)}
              className="flex items-center gap-2 px-3 py-2 bg-surface text-text-primary border border-border rounded-btns hover:bg-surface-highlight transition-colors text-sm"
            >
              <Zap className="w-4 h-4" />
              Load Preset
              <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", presetOpen && "rotate-180")} />
            </button>
            {presetOpen && (
              <div className="absolute right-0 top-full mt-1 w-64 bg-surface border border-border rounded-cards shadow-soft z-20 overflow-hidden">
                {Object.entries(PRESET_PROFILES).map(([key, profile]) => (
                  <button
                    key={key}
                    onClick={() => {
                      loadPreset(key);
                      setPresetOpen(false);
                    }}
                    className="w-full text-left px-4 py-3 hover:bg-surface-highlight transition-colors border-b border-border/50 last:border-0"
                  >
                    <div className="text-sm font-medium text-white">{profile.label}</div>
                    <div className="text-xs text-text-muted mt-0.5">{profile.description}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-3 py-2 bg-surface text-text-primary border border-border rounded-btns hover:bg-surface-highlight transition-colors text-sm"
          >
            <Download className="w-4 h-4" /> Export
          </button>
        </div>
      </div>

      {/* Active Config Status Bar */}
      {activeConfig && (
        <div className="bg-surface-base border border-border rounded-cards px-5 py-3 flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-2">
            <Check className="w-3.5 h-3.5 text-profit" />
            <span className="text-text-muted">Active Config</span>
            <span className="font-mono font-bold text-white">v{activeConfig.version}</span>
          </div>
          <div className="h-4 w-px bg-border hidden sm:block" />
          <div className="flex items-center gap-1.5">
            <Clock className="w-3 h-3 text-text-dim" />
            <span className="text-text-muted">
              {new Date(activeConfig.created_at).toLocaleString()}
            </span>
          </div>
          <div className="h-4 w-px bg-border hidden sm:block" />
          <div className="text-text-muted">
            by <span className="text-text-secondary">{activeConfig.created_by}</span>
          </div>
          <div className="h-4 w-px bg-border hidden sm:block" />
          <div className="font-mono text-text-dim">{activeConfig.checksum}</div>
        </div>
      )}

      {/* Kill Switch + Trading Enabled */}
      <div className="bg-surface border border-border rounded-cards px-6 py-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {draftConfig.trading_enabled ? (
              <ToggleRight className="w-6 h-6 text-profit" />
            ) : (
              <ToggleLeft className="w-6 h-6 text-loss" />
            )}
            <div>
              <div className="text-sm font-semibold text-white">Trading Enabled</div>
              <div className="text-xs text-text-muted">Master kill switch — disables all trade execution</div>
            </div>
          </div>
          <button
            onClick={() => handleToggle("trading_enabled", !draftConfig.trading_enabled)}
            className={cn(
              "relative w-14 h-7 rounded-full transition-colors duration-200",
              draftConfig.trading_enabled
                ? "bg-profit/30 border border-profit/40"
                : "bg-loss/20 border border-loss/30"
            )}
          >
            <div
              className={cn(
                "absolute top-0.5 w-6 h-6 rounded-full transition-all duration-200",
                draftConfig.trading_enabled
                  ? "translate-x-7 bg-profit"
                  : "translate-x-0.5 bg-loss"
              )}
            />
          </button>
        </div>
      </div>

      {/* Dial Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk */}
        <DialCard title="Risk Management" icon={Shield}>
          <DialSlider path="risk.risk_per_trade_pct" config={draftConfig} onChange={handleDialChange} error={errorMap["risk.risk_per_trade_pct"]} />
          <DialSlider path="risk.max_notional_exposure_pct" config={draftConfig} onChange={handleDialChange} error={errorMap["risk.max_notional_exposure_pct"]} />
        </DialCard>

        {/* Signals */}
        <DialCard title="Signal Thresholds" icon={Target}>
          <DialSlider path="signals.min_signal_score" config={draftConfig} onChange={handleDialChange} error={errorMap["signals.min_signal_score"]} />
          <DialSlider path="signals.confirmations_required" config={draftConfig} onChange={handleDialChange} error={errorMap["signals.confirmations_required"]} />
        </DialCard>

        {/* Exits */}
        <DialCard title="Exit Rules" icon={Activity}>
          <DialSlider path="exits.tp_pct" config={draftConfig} onChange={handleDialChange} error={errorMap["exits.tp_pct"]} />
          <DialSlider path="exits.stop.atr_mult" config={draftConfig} onChange={handleDialChange} error={errorMap["exits.stop.atr_mult"]} />
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm font-medium text-text-secondary">Stop Method</span>
            <div className="flex gap-2">
              {(["ATR", "percent"] as const).map((method) => (
                <button
                  key={method}
                  onClick={() => {
                    const clone = JSON.parse(JSON.stringify(draftConfig)) as StrategyConfig;
                    clone.exits.stop.method = method;
                    setDraftConfig(clone);
                  }}
                  className={cn(
                    "px-3 py-1 rounded-btns text-xs font-medium transition-colors",
                    draftConfig.exits.stop.method === method
                      ? "bg-white/10 text-white border border-border-strong"
                      : "bg-surface-base text-text-dim border border-border hover:text-text-muted"
                  )}
                >
                  {method}
                </button>
              ))}
            </div>
          </div>
        </DialCard>

        {/* Execution */}
        <DialCard title="Execution" icon={Zap}>
          <DialSlider path="execution.max_spread_pct_to_trade" config={draftConfig} onChange={handleDialChange} error={errorMap["execution.max_spread_pct_to_trade"]} />
          <DialSlider path="execution.limit_chase.max_cross_pct" config={draftConfig} onChange={handleDialChange} error={errorMap["execution.limit_chase.max_cross_pct"]} />
          <ToggleDial
            label="Limit Chase Enabled"
            value={draftConfig.execution.limit_chase.enabled}
            onChange={(v) => handleToggle("execution.limit_chase.enabled", v)}
            tooltip="When enabled, the bot will chase fills by adjusting limit orders."
          />
        </DialCard>

        {/* Timing */}
        <DialCard title="Timing & Cooldowns" icon={Clock}>
          <DialSlider path="timing.time_stop_hours" config={draftConfig} onChange={handleDialChange} error={errorMap["timing.time_stop_hours"]} />
          <DialSlider path="timing.cooldown_minutes" config={draftConfig} onChange={handleDialChange} error={errorMap["timing.cooldown_minutes"]} />
          <DialSlider path="timing.cooldown_after_loss_multiplier" config={draftConfig} onChange={handleDialChange} error={errorMap["timing.cooldown_after_loss_multiplier"]} />
        </DialCard>

        {/* Gates */}
        <DialCard title="Safety Gates" icon={AlertTriangle}>
          <DialSlider path="gates.vol_halt_24h_range" config={draftConfig} onChange={handleDialChange} error={errorMap["gates.vol_halt_24h_range"]} />
          <DialSlider path="gates.max_trades_per_hour" config={draftConfig} onChange={handleDialChange} error={errorMap["gates.max_trades_per_hour"]} />
        </DialCard>
      </div>

      {/* Strategy Toggles */}
      <DialCard title="Strategy Selection" icon={Target}>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {(
            [
              { key: "bounce_enabled", label: "Bounce Catcher", weightKey: "bounce" },
              { key: "trend_follow_enabled", label: "Trend Follow", weightKey: "trend_follow" },
              { key: "mean_reversion_enabled", label: "Mean Reversion", weightKey: "mean_reversion" },
            ] as const
          ).map(({ key, label, weightKey }) => {
            const enabled = draftConfig.strategies[key];
            const weight = draftConfig.strategies.weights[weightKey];
            return (
              <div
                key={key}
                className={cn(
                  "bg-surface-base border rounded-btns p-4 space-y-3 transition-colors",
                  enabled ? "border-profit/20" : "border-border"
                )}
              >
                <ToggleDial
                  label={label}
                  value={enabled}
                  onChange={(v) => handleToggle(`strategies.${key}`, v)}
                />
                <div>
                  <div className="flex justify-between text-xs text-text-dim mb-1">
                    <span>Weight</span>
                    <span className="font-mono">{(weight * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={weight}
                    disabled={!enabled}
                    onChange={(e) => handleDialChange(`strategies.weights.${weightKey}`, parseFloat(e.target.value))}
                    className="w-full h-1 bg-surface-highlight rounded-full appearance-none cursor-pointer disabled:opacity-30
                      [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3
                      [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:cursor-pointer"
                  />
                </div>
              </div>
            );
          })}
        </div>
        {errorMap["strategies.weights"] && (
          <p className="text-xs text-loss font-medium mt-2">{errorMap["strategies.weights"]}</p>
        )}
      </DialCard>

      {/* Save Bar */}
      {(hasChanges || errors.length > 0) && (
        <div className="sticky bottom-4 z-30">
          <div className={cn(
            "flex items-center justify-between px-6 py-4 rounded-cards border shadow-soft backdrop-blur-xl",
            errors.length > 0
              ? "bg-loss/10 border-loss/20"
              : "bg-surface/90 border-profit/20"
          )}>
            <div className="flex items-center gap-3">
              {errors.length > 0 ? (
                <AlertTriangle className="w-4 h-4 text-loss" />
              ) : (
                <Save className="w-4 h-4 text-profit" />
              )}
              <span className="text-sm text-text-secondary">
                {errors.length > 0
                  ? `${errors.length} validation error${errors.length > 1 ? "s" : ""}`
                  : "Unsaved changes"}
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={resetDraft}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-text-secondary hover:text-white transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset
              </button>
              <button
                onClick={() => setShowDiffPreview(true)}
                disabled={errors.length > 0}
                className={cn(
                  "flex items-center gap-1.5 px-4 py-1.5 rounded-btns text-sm font-bold transition-all",
                  errors.length > 0
                    ? "bg-surface-highlight text-text-dim cursor-not-allowed"
                    : "bg-profit/20 text-profit border border-profit/30 hover:bg-profit/30"
                )}
              >
                <Save className="w-3.5 h-3.5" />
                Review & Save
              </button>
            </div>
          </div>
        </div>
      )}

      {saveError && (
        <div className="bg-loss/10 border border-loss/20 rounded-btns px-4 py-3 text-sm text-loss">
          Save failed: {saveError}
        </div>
      )}

      {/* Recent Config Changes */}
      {auditLog.length > 0 && (
        <div className="bg-surface border border-border rounded-cards overflow-hidden">
          <div className="px-6 py-4 border-b border-border bg-surface-highlight/20 flex items-center gap-2">
            <Clock className="w-4 h-4 text-text-muted" />
            <h3 className="font-medium text-sm">Recent Config Changes</h3>
          </div>
          <div className="divide-y divide-border max-h-80 overflow-auto">
            {auditLog.map((entry) => {
              const diffEntries = Object.entries(entry.diff_json);
              return (
                <div key={entry.id} className="px-6 py-3 hover:bg-surface-highlight/20 transition-colors">
                  <div className="flex items-center gap-3 text-xs">
                    <span className="font-mono font-bold text-white">v{entry.version}</span>
                    <span className="text-text-dim">
                      {new Date(entry.changed_at).toLocaleString()}
                    </span>
                    <span className="text-text-muted">by {entry.changed_by}</span>
                    {entry.reason && (
                      <span className="text-text-secondary italic">— {entry.reason}</span>
                    )}
                  </div>
                  {diffEntries.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-2">
                      {diffEntries.slice(0, 4).map(([key, { old: o, new: n }]) => (
                        <span key={key} className="text-[10px] font-mono bg-surface-base px-2 py-0.5 rounded border border-border">
                          {key.split(".").pop()}:{" "}
                          <span className="text-loss">{formatDialValue(key, o)}</span>
                          →
                          <span className="text-profit">{formatDialValue(key, n)}</span>
                        </span>
                      ))}
                      {diffEntries.length > 4 && (
                        <span className="text-[10px] text-text-dim">+{diffEntries.length - 4} more</span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Admin Actions */}
      <div className="bg-surface border border-border rounded-cards p-6">
        <h3 className="font-medium text-sm mb-4 text-text-secondary">Admin Actions</h3>
        <div className="flex gap-4 flex-wrap">
          {!killConfirm ? (
            <button
              onClick={() => setKillConfirm(true)}
              className="flex items-center gap-2 px-4 py-2 bg-loss/10 text-loss border border-loss/20 rounded-btns hover:bg-loss/20 transition-colors text-sm font-medium"
            >
              <AlertTriangle className="w-4 h-4" /> Emergency Kill Switch
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-loss font-bold">This pauses all trading. Confirm?</span>
              <button
                onClick={async () => {
                  try {
                    if (draftConfig) {
                      const clone = { ...draftConfig, trading_enabled: false };
                      setDraftConfig(clone);
                    }
                    await supabase.from("config").upsert({ key: "kill_switch", value: true, instance_id: MODE });
                    setKillConfirm(false);
                  } catch {
                    // ignore
                  }
                }}
                className="px-3 py-1.5 bg-loss text-white rounded-btns text-sm font-bold"
              >
                CONFIRM KILL
              </button>
              <button
                onClick={() => setKillConfirm(false)}
                className="px-3 py-1.5 bg-surface-highlight text-text-secondary rounded-btns text-sm"
              >
                Cancel
              </button>
            </div>
          )}
          <button
            onClick={handleClearCache}
            className="flex items-center gap-2 px-4 py-2 bg-surface-highlight text-text-primary rounded-btns hover:bg-border transition-colors text-sm font-medium"
          >
            <Trash2 className="w-4 h-4" />
            {cacheCleared ? "Cache Cleared!" : "Clear Cache"}
          </button>
        </div>
      </div>

      {/* Diff Preview Modal */}
      {showDiffPreview && (
        <DiffPreview
          prev={activeConfig?.config_json ?? null}
          next={draftConfig}
          onConfirm={handleSave}
          onCancel={() => setShowDiffPreview(false)}
          saving={saving}
          isLive={!isPaper}
        />
      )}
    </div>
  );
}
