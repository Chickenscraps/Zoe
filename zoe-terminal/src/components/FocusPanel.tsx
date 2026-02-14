import { TrendingUp, TrendingDown, Minus, Star } from "lucide-react";
import { cn } from "../lib/utils";
import { useFocusData } from "../hooks/useMarketData";
import type { Database } from "../lib/types";

type FocusRow = Database["public"]["Tables"]["market_snapshot_focus"]["Row"];

function formatPrice(price: number): string {
  if (price === 0) return "-";
  if (price >= 1000) return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (price >= 1) return price.toFixed(4);
  return price.toFixed(6);
}

export default function FocusPanel() {
  const { data, loading } = useFocusData();

  if (loading) {
    return (
      <div className="border border-border bg-surface-base p-4">
        <div className="flex items-center gap-2 mb-3">
          <Star className="w-4 h-4 text-sakura-500" />
          <h3 className="text-sm font-semibold text-text-primary">Live Prices</h3>
        </div>
        <div className="text-xs text-text-muted">Loading...</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="border border-border bg-surface-base p-4">
        <div className="flex items-center gap-2 mb-3">
          <Star className="w-4 h-4 text-sakura-500" />
          <h3 className="text-sm font-semibold text-text-primary">Live Prices</h3>
        </div>
        <div className="text-xs text-text-muted">
          No focus data yet. Start the Market Data WS service to see live prices.
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border bg-surface-base p-4">
      <div className="flex items-center gap-2 mb-3">
        <Star className="w-4 h-4 text-sakura-500" />
        <h3 className="text-sm font-semibold text-text-primary">Live Prices</h3>
        <span className="text-xs text-text-muted ml-auto">{data.length} pairs</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-2">
        {data.map((row) => (
          <FocusTile key={row.symbol} row={row} />
        ))}
      </div>
    </div>
  );
}

function FocusTile({ row }: { row: FocusRow }) {
  const base = row.symbol.split("-")[0];
  const changeColor =
    row.change_24h_pct > 0
      ? "text-profit"
      : row.change_24h_pct < 0
        ? "text-loss"
        : "text-text-muted";

  const Icon =
    row.change_24h_pct > 0
      ? TrendingUp
      : row.change_24h_pct < 0
        ? TrendingDown
        : Minus;

  return (
    <div className="bg-background/50 border border-border/50 px-3 py-2 hover:border-sakura-500/30 transition-colors">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold text-text-primary">{base}</span>
        <span className={cn("flex items-center gap-0.5 text-xs font-mono", changeColor)}>
          <Icon className="w-3 h-3" />
          {row.change_24h_pct >= 0 ? "+" : ""}
          {row.change_24h_pct.toFixed(2)}%
        </span>
      </div>
      <div className="text-sm font-mono text-text-primary">{formatPrice(row.mid)}</div>
      <div className="flex items-center justify-between text-[10px] text-text-muted mt-0.5">
        <span>Spread: {row.spread_pct > 0 ? `${row.spread_pct.toFixed(3)}%` : "-"}</span>
      </div>
    </div>
  );
}
