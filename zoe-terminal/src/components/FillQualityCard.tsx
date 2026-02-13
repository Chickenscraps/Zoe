/**
 * Fill Quality card — shows rolling average implementation shortfall.
 *
 * Displays on the Trades page:
 * - Rolling avg IS (absolute bps)
 * - Directional IS (positive = slippage cost, negative = improvement)
 * - Fill count
 * - Recent fill list with per-fill IS
 *
 * Thresholds: Green <10bps | Yellow 10-25bps | Red >25bps
 *
 * References: [AA] §4.1, §4.3
 */
import { TrendingDown, TrendingUp, Target } from 'lucide-react';
import { cn } from '../lib/utils';
import type { FillQualityData } from '../hooks/useSystemHealth';

interface FillQualityCardProps {
  fillQuality: FillQualityData;
}

export function FillQualityCard({ fillQuality }: FillQualityCardProps) {
  const { avgIsBps, directionalIsBps, fillCount, recentFills } = fillQuality;

  const status = avgIsBps < 10 ? 'ok' : avgIsBps < 25 ? 'warning' : 'error';
  const statusColors = {
    ok: 'text-profit',
    warning: 'text-yellow-400',
    error: 'text-loss',
  };
  const statusBg = {
    ok: 'bg-profit/10 border-profit/20',
    warning: 'bg-yellow-500/10 border-yellow-500/20',
    error: 'bg-loss/10 border-loss/20',
  };

  return (
    <div className="card-premium p-4 sm:p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-text-muted" />
          <h3 className="text-sm font-bold text-white tracking-tight">Fill Quality</h3>
        </div>
        <span className="text-[9px] text-text-muted uppercase tracking-widest font-medium">
          {fillCount} fills
        </span>
      </div>

      {fillCount === 0 ? (
        <div className="text-center py-6 text-text-muted text-xs italic">
          No fill quality data yet
        </div>
      ) : (
        <>
          {/* Main IS metrics */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            {/* Avg IS (absolute) */}
            <div className={cn("rounded-lg border p-3", statusBg[status])}>
              <div className="text-[9px] uppercase tracking-widest font-bold text-text-muted mb-1">
                Avg IS
              </div>
              <div className={cn("text-xl font-black font-mono", statusColors[status])}>
                {avgIsBps.toFixed(1)}
                <span className="text-[10px] font-bold ml-0.5">bps</span>
              </div>
            </div>

            {/* Directional IS */}
            <div className="rounded-lg border border-border bg-surface-base/50 p-3">
              <div className="text-[9px] uppercase tracking-widest font-bold text-text-muted mb-1">
                Direction
              </div>
              <div className={cn(
                "text-xl font-black font-mono flex items-center gap-1",
                directionalIsBps > 0 ? "text-loss" : directionalIsBps < 0 ? "text-profit" : "text-text-muted"
              )}>
                {directionalIsBps > 0 ? (
                  <TrendingUp className="w-4 h-4" />
                ) : directionalIsBps < 0 ? (
                  <TrendingDown className="w-4 h-4" />
                ) : null}
                {directionalIsBps > 0 ? '+' : ''}{directionalIsBps.toFixed(1)}
                <span className="text-[10px] font-bold ml-0.5">bps</span>
              </div>
              <div className="text-[9px] text-text-muted mt-0.5">
                {directionalIsBps > 0 ? 'Slippage cost' : directionalIsBps < 0 ? 'Price improvement' : 'Neutral'}
              </div>
            </div>
          </div>

          {/* Recent fills mini-table */}
          {recentFills.length > 0 && (
            <div>
              <div className="text-[9px] uppercase tracking-widest font-bold text-text-muted mb-2">
                Recent Fills
              </div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {recentFills.slice(0, 8).map((fill, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-[11px] px-2 py-1 rounded bg-surface-base/30"
                  >
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "uppercase font-bold text-[9px]",
                        fill.side === 'buy' ? 'text-profit' : 'text-loss'
                      )}>
                        {fill.side}
                      </span>
                      <span className="text-text-primary font-medium">{fill.symbol}</span>
                    </div>
                    <span className={cn(
                      "font-mono font-bold",
                      fill.isBps > 10 ? 'text-loss' : fill.isBps < -5 ? 'text-profit' : 'text-text-muted'
                    )}>
                      {fill.isBps > 0 ? '+' : ''}{fill.isBps.toFixed(1)} bps
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
