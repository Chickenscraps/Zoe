import { Coins, DollarSign, TrendingUp, Wallet } from "lucide-react";
import { EquityChart } from "../components/EquityChart";
import { KPICard } from "../components/KPICard";

import { PositionsTable } from "../components/PositionsTable";
import { Skeleton } from "../components/Skeleton";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatCurrency, cn } from "../lib/utils";
import { useMemo } from "react";

export default function Overview() {
  const {
    cryptoCash,
    holdingsRows,
    livePrices,
    equityHistory,
    initialDeposit,
    loading,
  } = useDashboardData();

  // Cash from latest snapshot
  const cashValue = cryptoCash?.buying_power ?? 0;

  // Compute crypto value: sum holdings * live prices
  const cryptoValue = useMemo(() => {
    if (!holdingsRows.length || !livePrices.length) return 0;
    let total = 0;
    for (const row of holdingsRows) {
      // Find matching live price from scans
      const scan = livePrices.find(s => s.symbol === row.asset);
      const mid = scan ? ((scan.info as any)?.mid ?? 0) : 0;
      total += row.qty * mid;
    }
    return total;
  }, [holdingsRows, livePrices]);

  const totalValue = cashValue + cryptoValue;

  // P&L calculations
  const allTimePnl = initialDeposit > 0 ? totalValue - initialDeposit : 0;
  const allTimePnlPct = initialDeposit > 0 ? ((totalValue - initialDeposit) / initialDeposit) * 100 : 0;

  // Daily P&L: today's total portfolio value vs start-of-day equity
  const dailyPnl = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    const pastPoints = equityHistory.filter(p => p.date < today);
    if (pastPoints.length > 0) {
      const yesterdayEquity = pastPoints[pastPoints.length - 1].equity;
      return totalValue - yesterdayEquity;
    }
    return allTimePnl;
  }, [equityHistory, totalValue, allTimePnl]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
        <KPICard
          label="Crypto"
          value={formatCurrency(cryptoValue)}
          subValue={holdingsRows.length > 0 ? `${holdingsRows.length} position${holdingsRows.length !== 1 ? 's' : ''}` : "No positions"}
          trend={cryptoValue > 0 ? "Invested" : "Empty"}
          trendDir={cryptoValue > 0 ? 'up' : 'neutral'}
          icon={Coins}
          className="card-stagger"
          style={{ '--stagger-delay': '0ms' } as React.CSSProperties}
        />
        <KPICard
          label="Cash"
          value={formatCurrency(cashValue)}
          subValue="Available Balance"
          trend={totalValue > 0 ? ((cashValue / totalValue) * 100).toFixed(1) + "% of total" : "—"}
          trendDir="neutral"
          icon={Wallet}
          className="card-stagger"
          style={{ '--stagger-delay': '80ms' } as React.CSSProperties}
        />
        <KPICard
          label="Total"
          value={formatCurrency(totalValue)}
          subValue="Portfolio Value"
          trend={allTimePnl !== 0 ? `${allTimePnl >= 0 ? '+' : ''}${formatCurrency(allTimePnl)} P&L` : "—"}
          trendDir={allTimePnl >= 0 ? 'up' : 'down'}
          icon={DollarSign}
          className="card-stagger"
          style={{ '--stagger-delay': '160ms' } as React.CSSProperties}
        />
      </div>

      {/* Open Positions */}
      <PositionsTable />

      {/* Equity Curve with Day + Overall P&L */}
      <EquityChart
        data={equityHistory}
        dailyPnl={dailyPnl}
        allTimePnl={allTimePnl}
        allTimePnlPct={allTimePnlPct}
        height={280}
      />

      {/* Live Crypto Prices */}
      {livePrices.length > 0 && (
        <div className="bg-paper-100/80 border-2 border-earth-700/10 rounded-[4px] p-4 sm:p-6">
          <div className="flex items-center justify-between mb-3 sm:mb-4">
            <h3 className="font-pixel text-[0.4rem] uppercase tracking-[0.08em] text-text-muted flex items-center gap-2">
              <TrendingUp className="w-3 h-3 text-sakura-700" /> Live Prices
            </h3>
            <span className="text-[9px] font-bold text-text-dim uppercase tracking-widest">
              {livePrices[0]?.created_at ? new Date(livePrices[0].created_at).toLocaleTimeString([], { hour12: false }) : ''}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 sm:gap-3">
            {livePrices.slice(0, 10).map((scan, i) => {
              const info = scan.info as any ?? {};
              const mid = info.mid ?? 0;
              const momShort = info.momentum_short;
              const isUp = momShort != null ? momShort >= 0 : true;
              return (
                <div
                  key={scan.symbol}
                  className="flex flex-col items-center p-2.5 sm:p-3 bg-cream-100/60 border-2 border-earth-700/10 rounded-[4px] hover:border-sakura-500/30 transition-all duration-200 card-stagger"
                  style={{ '--stagger-delay': `${i * 50}ms` } as React.CSSProperties}
                >
                  <span className="text-[9px] sm:text-[10px] font-black text-text-muted uppercase tracking-widest mb-1">
                    {scan.symbol.replace('-USD', '')}
                  </span>
                  <span className="text-xs sm:text-sm font-bold text-earth-700 tabular-nums">
                    {mid >= 1 ? `$${mid.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : `$${mid.toFixed(6)}`}
                  </span>
                  {momShort != null && (
                    <span className={cn(
                      "text-[9px] sm:text-[10px] font-bold tabular-nums mt-0.5",
                      isUp ? "text-profit" : "text-loss"
                    )}>
                      {isUp ? '▲' : '▼'} {Math.abs(momShort).toFixed(3)}%
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
