import { useState, useMemo } from "react";
import {
  Search,
  TrendingUp,
  TrendingDown,
  Star,
  Zap,
  ArrowUpDown,
  Globe,
  Minus,
} from "lucide-react";
import { cn } from "../lib/utils";
import { useMarketData, useMoverAlerts, type MarketRow } from "../hooks/useMarketData";

type Tab = "all" | "gainers" | "losers" | "movers" | "focus";
type SortKey = "symbol" | "mid" | "change_24h_pct" | "volume_24h" | "spread_pct";

const TABS: { value: Tab; label: string; icon: React.ReactNode }[] = [
  { value: "all", label: "All", icon: <Globe className="w-3.5 h-3.5" /> },
  { value: "focus", label: "Focus", icon: <Star className="w-3.5 h-3.5" /> },
  { value: "gainers", label: "Gainers", icon: <TrendingUp className="w-3.5 h-3.5" /> },
  { value: "losers", label: "Losers", icon: <TrendingDown className="w-3.5 h-3.5" /> },
  { value: "movers", label: "Movers", icon: <Zap className="w-3.5 h-3.5" /> },
];

function formatPrice(price: number): string {
  if (price === 0) return "-";
  if (price >= 1000) return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (price >= 1) return price.toFixed(4);
  if (price >= 0.01) return price.toFixed(6);
  return price.toFixed(8);
}

function formatVolume(vol: number): string {
  if (vol === 0) return "-";
  if (vol >= 1_000_000_000) return `${(vol / 1_000_000_000).toFixed(1)}B`;
  if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(1)}M`;
  if (vol >= 1_000) return `${(vol / 1_000).toFixed(1)}K`;
  return vol.toFixed(0);
}

function formatChange(pct: number): string {
  if (pct === 0) return "0.00%";
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

export default function Markets() {
  const { rows, loading, focusCount, scoutCount } = useMarketData();
  const movers = useMoverAlerts(10);

  const [tab, setTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("volume_24h");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "symbol" ? "asc" : "desc");
    }
  };

  const filtered = useMemo(() => {
    let list = rows;

    // Tab filter
    if (tab === "focus") list = list.filter((r) => r.is_focus);
    if (tab === "gainers") list = list.filter((r) => r.change_24h_pct > 0);
    if (tab === "losers") list = list.filter((r) => r.change_24h_pct < 0);
    if (tab === "movers") {
      const moverSyms = new Set(movers.map((m) => m.symbol));
      list = list.filter((r) => moverSyms.has(r.symbol));
    }

    // Search
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (r) =>
          r.symbol.toLowerCase().includes(q) ||
          r.base.toLowerCase().includes(q)
      );
    }

    // Sort
    list = [...list].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });

    return list;
  }, [rows, tab, search, sortKey, sortDir, movers]);

  const SortBtn = ({ col, label }: { col: SortKey; label: string }) => (
    <button
      className="flex items-center gap-1 hover:text-text-primary transition-colors"
      onClick={() => toggleSort(col)}
    >
      {label}
      <ArrowUpDown
        className={cn(
          "w-3 h-3",
          sortKey === col ? "text-accent" : "text-text-muted"
        )}
      />
    </button>
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Markets</h1>
          <p className="text-sm text-text-muted">
            {loading
              ? "Loading..."
              : `${rows.length} pairs (${focusCount} focus, ${scoutCount} scout)`}
          </p>
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search symbol..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface-card border border-border text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-surface-card rounded-lg border border-border w-fit">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
              tab === t.value
                ? "bg-accent/20 text-accent"
                : "text-text-muted hover:text-text-secondary"
            )}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Mover alerts banner */}
      {movers.length > 0 && tab !== "movers" && (
        <div className="flex items-center gap-2 px-3 py-2 bg-accent/10 border border-accent/20 rounded-lg text-xs text-accent">
          <Zap className="w-3.5 h-3.5" />
          <span>
            {movers.length} mover{movers.length > 1 ? "s" : ""} detected:{" "}
            {movers
              .slice(0, 3)
              .map((m) => `${m.symbol} ${m.direction === "up" ? "+" : "-"}${m.magnitude.toFixed(1)}%`)
              .join(", ")}
          </span>
          <button
            onClick={() => setTab("movers")}
            className="ml-auto text-accent hover:underline"
          >
            View
          </button>
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-card text-text-muted text-xs border-b border-border">
                <th className="text-left px-4 py-3 font-medium">
                  <SortBtn col="symbol" label="Symbol" />
                </th>
                <th className="text-right px-4 py-3 font-medium">
                  <SortBtn col="mid" label="Price" />
                </th>
                <th className="text-right px-4 py-3 font-medium">
                  <SortBtn col="change_24h_pct" label="24h Change" />
                </th>
                <th className="text-right px-4 py-3 font-medium">
                  <SortBtn col="volume_24h" label="Volume" />
                </th>
                <th className="text-right px-4 py-3 font-medium">
                  <SortBtn col="spread_pct" label="Spread" />
                </th>
                <th className="text-right px-4 py-3 font-medium">Bid / Ask</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-text-muted">
                    No markets found
                  </td>
                </tr>
              )}
              {filtered.map((row) => (
                <MarketRowItem key={row.symbol} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MarketRowItem({ row }: { row: MarketRow }) {
  const changeColor =
    row.change_24h_pct > 0
      ? "text-profit"
      : row.change_24h_pct < 0
        ? "text-loss"
        : "text-text-muted";

  const ChangeIcon =
    row.change_24h_pct > 0
      ? TrendingUp
      : row.change_24h_pct < 0
        ? TrendingDown
        : Minus;

  return (
    <tr className="border-b border-border/50 hover:bg-surface-card/50 transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          {row.is_focus && (
            <Star className="w-3 h-3 text-accent fill-accent" />
          )}
          <span className="font-medium text-text-primary">{row.base}</span>
          <span className="text-text-muted text-xs">/ USD</span>
        </div>
      </td>
      <td className="text-right px-4 py-3 font-mono text-text-primary">
        {formatPrice(row.mid)}
      </td>
      <td className={cn("text-right px-4 py-3 font-mono", changeColor)}>
        <span className="flex items-center justify-end gap-1">
          <ChangeIcon className="w-3 h-3" />
          {formatChange(row.change_24h_pct)}
        </span>
      </td>
      <td className="text-right px-4 py-3 font-mono text-text-secondary">
        {formatVolume(row.volume_24h)}
      </td>
      <td className="text-right px-4 py-3 font-mono text-text-muted">
        {row.spread_pct > 0 ? `${row.spread_pct.toFixed(3)}%` : "-"}
      </td>
      <td className="text-right px-4 py-3 text-xs text-text-muted font-mono">
        {row.bid > 0 ? (
          <>
            <span className="text-profit">{formatPrice(row.bid)}</span>
            {" / "}
            <span className="text-loss">{formatPrice(row.ask)}</span>
          </>
        ) : (
          "-"
        )}
      </td>
    </tr>
  );
}
