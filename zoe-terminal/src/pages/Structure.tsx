/**
 * Structure page — visualizes trendlines, horizontal levels, pivots,
 * structure events, bounce state machine, and trade intents.
 */

import { useState } from "react";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Zap,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  RotateCcw,
  ShieldCheck,
  ShieldX,
  CircleDot,
} from "lucide-react";
import { useStructureData, type BounceIntent } from "../hooks/useStructureData";
import { formatCurrency, cn } from "../lib/utils";
import { Skeleton } from "../components/Skeleton";
import { StatusChip } from "../components/StatusChip";

const SYMBOLS = ["All", "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "AVAX-USD"];
const TIMEFRAMES = ["All", "15m", "1h", "4h", "1d"];

export default function Structure() {
  const [symbol, setSymbol] = useState("All");
  const [timeframe, setTimeframe] = useState("All");

  const {
    pivots,
    trendlines,
    levels,
    structureEvents,
    bounceEvents,
    bounceIntents,
    loading,
  } = useStructureData({
    symbol: symbol === "All" ? undefined : symbol,
    timeframe: timeframe === "All" ? undefined : timeframe,
  });

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Skeleton className="h-12" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-10">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">
            Symbol
          </span>
          <div className="flex flex-wrap gap-1">
            {SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className={cn(
                  "px-2 sm:px-3 py-1.5 rounded-btns text-[9px] sm:text-[10px] font-black uppercase tracking-wider transition-all",
                  symbol === s
                    ? "bg-text-primary text-background"
                    : "bg-surface-base border border-border text-text-secondary hover:text-white hover:border-border-strong"
                )}
              >
                {s.replace('-USD', '')}
              </button>
            ))}
          </div>
        </div>
        <div className="h-6 w-px bg-border hidden sm:block" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">
            TF
          </span>
          <div className="flex flex-wrap gap-1">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={cn(
                  "px-2 sm:px-3 py-1.5 rounded-btns text-[9px] sm:text-[10px] font-black uppercase tracking-wider transition-all",
                  timeframe === tf
                    ? "bg-text-primary text-background"
                    : "bg-surface-base border border-border text-text-secondary hover:text-white hover:border-border-strong"
                )}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary Bar */}
      <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2 sm:gap-4">
        <SummaryStat label="Trendlines" value={trendlines.length} icon={TrendingUp} />
        <SummaryStat label="Levels" value={levels.length} icon={Minus} />
        <SummaryStat label="Pivots" value={pivots.length} icon={CircleDot} />
        <SummaryStat label="Events" value={structureEvents.length} icon={Zap} />
        <SummaryStat label="Bounces" value={bounceEvents.length} icon={RotateCcw} />
        <SummaryStat label="Intents" value={bounceIntents.length} icon={Target} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-8">
        {/* Trendlines */}
        <div className="card-premium p-4 sm:p-8">
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
            <TrendingUp className="w-3 h-3 text-profit" /> Active Trendlines
          </h3>
          <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
            {trendlines.length > 0 ? (
              trendlines.map((tl) => (
                <div
                  key={tl.id}
                  className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2 sm:gap-3 bg-background/50 border border-border rounded-lg px-3 sm:px-4 py-2.5 sm:py-3 text-xs"
                >
                  <div className="flex items-center gap-2">
                    {tl.side === "support" ? (
                      <TrendingUp className="w-3 h-3 text-profit" />
                    ) : (
                      <TrendingDown className="w-3 h-3 text-loss" />
                    )}
                    <span className="font-black text-white">{tl.symbol}</span>
                    <span className="text-text-muted text-[10px] font-mono">{tl.timeframe}</span>
                  </div>
                  <span
                    className={cn(
                      "text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full",
                      tl.side === "support"
                        ? "bg-profit/10 text-profit"
                        : "bg-loss/10 text-loss"
                    )}
                  >
                    {tl.side}
                  </span>
                  <span className="font-mono text-text-secondary text-right">
                    {tl.inlier_count} pts
                  </span>
                  <ScoreBadge score={tl.score} />
                </div>
              ))
            ) : (
              <EmptyState text="No active trendlines detected yet" />
            )}
          </div>
        </div>

        {/* Horizontal Levels */}
        <div className="card-premium p-4 sm:p-8">
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
            <Minus className="w-3 h-3 text-warning" /> Key Levels
          </h3>
          <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
            {levels.length > 0 ? (
              levels.map((lv) => (
                <div
                  key={lv.id}
                  className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2 sm:gap-3 bg-background/50 border border-border rounded-lg px-3 sm:px-4 py-2.5 sm:py-3 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-black text-white">{lv.symbol}</span>
                    <span className="text-text-muted text-[10px] font-mono">{lv.timeframe}</span>
                  </div>
                  <span className="font-mono text-white font-bold">
                    {formatCurrency(lv.price_centroid)}
                  </span>
                  <span
                    className={cn(
                      "text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full",
                      lv.role === "support"
                        ? "bg-profit/10 text-profit"
                        : lv.role === "resistance"
                          ? "bg-loss/10 text-loss"
                          : "bg-warning/10 text-warning"
                    )}
                  >
                    {lv.role ?? "—"}
                  </span>
                  <span className="font-mono text-text-secondary">
                    {lv.touch_count}x
                  </span>
                  <ScoreBadge score={lv.score} />
                </div>
              ))
            ) : (
              <EmptyState text="No horizontal levels clustered yet" />
            )}
          </div>
        </div>

        {/* Structure Events */}
        <div className="card-premium p-4 sm:p-8">
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
            <Zap className="w-3 h-3 text-warning" /> Structure Events
          </h3>
          <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
            {structureEvents.length > 0 ? (
              structureEvents.map((ev) => (
                <div
                  key={ev.id}
                  className="flex items-center gap-3 bg-background/50 border border-border rounded-lg px-4 py-3"
                >
                  <EventIcon type={ev.event_type} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-black text-white">{ev.symbol}</span>
                      <span className="text-[10px] font-mono text-text-muted">{ev.timeframe}</span>
                      <span
                        className={cn(
                          "text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full",
                          ev.event_type === "breakout"
                            ? "bg-profit/10 text-profit"
                            : ev.event_type === "breakdown"
                              ? "bg-loss/10 text-loss"
                              : "bg-warning/10 text-warning"
                        )}
                      >
                        {ev.event_type}
                      </span>
                      {ev.confirmed && (
                        <StatusChip status="ok" label="CONFIRMED" />
                      )}
                    </div>
                    <div className="text-[10px] text-text-muted font-mono mt-1">
                      @ {formatCurrency(ev.price_at)} &middot;{" "}
                      {new Date(ev.ts).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: false,
                      })}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState text="No structure events recorded yet" />
            )}
          </div>
        </div>

        {/* Bounce State Machine */}
        <div className="card-premium p-4 sm:p-8">
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
            <RotateCcw className="w-3 h-3 text-profit" /> Bounce State Machine
          </h3>
          <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
            {bounceEvents.length > 0 ? (
              bounceEvents.map((be) => (
                <div
                  key={be.id}
                  className="flex items-center gap-3 bg-background/50 border border-border rounded-lg px-4 py-3"
                >
                  <BounceStateIcon state={be.state} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-black text-white">{be.symbol}</span>
                      <span className="text-[10px] font-mono text-text-muted">
                        {be.prev_state ? `${be.prev_state} →` : "→"} {be.state}
                      </span>
                      {be.score != null && <ScoreBadge score={be.score} />}
                    </div>
                    <div className="text-[10px] text-text-muted font-mono mt-1">
                      {new Date(be.ts).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: false,
                      })}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState text="Bounce catcher awaiting first capitulation signal" />
            )}
          </div>
        </div>
      </div>

      {/* Trade Intents (full width) */}
      <div className="card-premium p-4 sm:p-8">
        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
          <Target className="w-3 h-3 text-profit" /> Trade Intents
        </h3>
        <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
          {bounceIntents.length > 0 ? (
            bounceIntents.map((intent) => (
              <IntentRow key={intent.id} intent={intent} />
            ))
          ) : (
            <EmptyState text="No trade intents emitted yet" />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────

function SummaryStat({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}) {
  return (
    <div className="card-premium p-4 flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-surface-highlight flex items-center justify-center">
        <Icon size={14} className="text-text-secondary" />
      </div>
      <div>
        <div className="text-lg font-black text-white font-mono">{value}</div>
        <div className="text-[10px] font-bold text-text-muted uppercase tracking-widest">{label}</div>
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 70
      ? "bg-profit/10 text-profit"
      : score >= 40
        ? "bg-warning/10 text-warning"
        : "bg-loss/10 text-loss";
  return (
    <span className={cn("text-[10px] font-black font-mono px-2 py-0.5 rounded-full", color)}>
      {score.toFixed(0)}
    </span>
  );
}

function EventIcon({ type }: { type: "breakout" | "breakdown" | "retest" }) {
  const cls = "w-7 h-7 rounded-full flex items-center justify-center";
  switch (type) {
    case "breakout":
      return (
        <div className={cn(cls, "bg-profit/10")}>
          <ArrowUpRight size={14} className="text-profit" />
        </div>
      );
    case "breakdown":
      return (
        <div className={cn(cls, "bg-loss/10")}>
          <ArrowDownRight size={14} className="text-loss" />
        </div>
      );
    case "retest":
      return (
        <div className={cn(cls, "bg-warning/10")}>
          <RotateCcw size={14} className="text-warning" />
        </div>
      );
  }
}

function BounceStateIcon({ state }: { state: string }) {
  const cls = "w-7 h-7 rounded-full flex items-center justify-center";
  switch (state.toLowerCase()) {
    case "capitulation_detected":
      return (
        <div className={cn(cls, "bg-loss/10")}>
          <ArrowDownRight size={14} className="text-loss" />
        </div>
      );
    case "stabilization_confirmed":
      return (
        <div className={cn(cls, "bg-warning/10")}>
          <ShieldCheck size={14} className="text-warning" />
        </div>
      );
    case "idle":
      return (
        <div className={cn(cls, "bg-surface-highlight")}>
          <Minus size={14} className="text-text-muted" />
        </div>
      );
    default:
      return (
        <div className={cn(cls, "bg-surface-highlight")}>
          <CircleDot size={14} className="text-text-secondary" />
        </div>
      );
  }
}

function IntentRow({ intent }: { intent: BounceIntent }) {
  return (
    <div className="flex flex-wrap items-center gap-3 sm:gap-4 bg-background/50 border border-border rounded-lg px-3 sm:px-5 py-3 sm:py-4 text-xs">
      {/* Status icon */}
      <div className="w-7 h-7 rounded-full flex items-center justify-center">
        {intent.blocked ? (
          <div className="w-7 h-7 rounded-full bg-loss/10 flex items-center justify-center">
            <ShieldX size={14} className="text-loss" />
          </div>
        ) : intent.executed ? (
          <div className="w-7 h-7 rounded-full bg-profit/10 flex items-center justify-center">
            <ShieldCheck size={14} className="text-profit" />
          </div>
        ) : (
          <div className="w-7 h-7 rounded-full bg-warning/10 flex items-center justify-center">
            <Target size={14} className="text-warning" />
          </div>
        )}
      </div>

      {/* Symbol + Style */}
      <div>
        <div className="flex items-center gap-2">
          <span className="font-black text-white">{intent.symbol}</span>
          <span className="text-[10px] text-text-muted font-mono uppercase">{intent.entry_style}</span>
        </div>
        <div className="text-[10px] text-text-muted font-mono mt-0.5">
          {new Date(intent.ts).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          })}
        </div>
      </div>

      {/* Entry */}
      <div className="text-right">
        <div className="text-[10px] text-text-muted uppercase tracking-wider">Entry</div>
        <div className="font-mono font-bold text-white">
          {intent.entry_price ? formatCurrency(intent.entry_price) : "—"}
        </div>
      </div>

      {/* TP */}
      <div className="text-right">
        <div className="text-[10px] text-text-muted uppercase tracking-wider">TP</div>
        <div className="font-mono font-bold text-profit">
          {intent.tp_price ? formatCurrency(intent.tp_price) : "—"}
        </div>
      </div>

      {/* SL */}
      <div className="text-right">
        <div className="text-[10px] text-text-muted uppercase tracking-wider">SL</div>
        <div className="font-mono font-bold text-loss">
          {intent.sl_price ? formatCurrency(intent.sl_price) : "—"}
        </div>
      </div>

      {/* Score + Status */}
      <div className="flex flex-col items-end gap-1">
        {intent.score != null && <ScoreBadge score={intent.score} />}
        <span
          className={cn(
            "text-[10px] font-black uppercase tracking-wider",
            intent.blocked
              ? "text-loss"
              : intent.executed
                ? "text-profit"
                : "text-warning"
          )}
        >
          {intent.blocked
            ? "BLOCKED"
            : intent.executed
              ? "EXECUTED"
              : "PENDING"}
        </span>
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center py-8 text-text-muted/60 text-xs italic">
      {text}
    </div>
  );
}
