import { DollarSign } from "lucide-react";
import { AlertBanner } from "../components/AlertBanner";
import { EquityChart } from "../components/EquityChart";
import { KPICard } from "../components/KPICard";

import { OpenOrdersTable } from "../components/OpenOrdersTable";
import { PositionsTable } from "../components/PositionsTable";
import { Skeleton } from "../components/Skeleton";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatCurrency } from "../lib/utils";
import { useMemo } from "react";

export default function Overview() {
  const {
    cryptoCash,
    cryptoOrders,
    holdingsRows,
    priceMap,
    equityHistory,
    initialDeposit,
    loading,
    error,
  } = useDashboardData();

  // Cash from latest snapshot
  const cashValue = cryptoCash?.cash_available ?? cryptoCash?.buying_power ?? 0;

  // Compute crypto value: sum holdings * live prices (priceMap merges candidate_scans + focus)
  const cryptoValue = useMemo(() => {
    if (!holdingsRows.length || !Object.keys(priceMap).length) return 0;
    let total = 0;
    for (const row of holdingsRows) {
      const mid = priceMap[row.asset] ?? 0;
      total += row.qty * mid;
    }
    return total;
  }, [holdingsRows, priceMap]);

  // Money allocated to pending buy orders (reserved by broker, not in cash balance)
  const pendingBuyNotional = useMemo(() => {
    if (!cryptoOrders?.length) return 0;
    return cryptoOrders
      .filter(o => ['new', 'submitted', 'partially_filled'].includes(o.status) && o.side === 'buy')
      .reduce((sum, o) => sum + (o.notional ?? 0), 0);
  }, [cryptoOrders]);

  const totalValue = cashValue + cryptoValue + pendingBuyNotional;

  // P&L calculations — guard against NaN/Infinity
  const allTimePnl = initialDeposit > 0 ? totalValue - initialDeposit : 0;
  const rawPct = initialDeposit > 0 ? ((totalValue - initialDeposit) / initialDeposit) * 100 : 0;
  const allTimePnlPct = isFinite(rawPct) ? rawPct : 0;

  // Daily P&L: today's total portfolio value vs start-of-day equity
  const dailyPnl = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    const pastPoints = equityHistory.filter(p => p.date < today);
    if (pastPoints.length > 0) {
      const yesterdayEquity = pastPoints[pastPoints.length - 1].equity;
      const result = totalValue - yesterdayEquity;
      return isFinite(result) ? result : 0;
    }
    return allTimePnl;
  }, [equityHistory, totalValue, allTimePnl]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Skeleton className="h-32" />
        <Skeleton className="h-80" />
      </div>
    );
  }

  const hasNoData = !cryptoCash && !holdingsRows.length && !cryptoOrders?.length && !equityHistory.length;

  return (
    <div className="space-y-8">
      {/* Alert Banners */}
      <AlertBanner />

      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          <span className="font-bold">Connection Error:</span> {error}
        </div>
      )}

      {/* Empty state when no trading data exists yet */}
      {hasNoData && !error && (
        <div className="rounded-lg border border-amber-400/20 bg-amber-500/5 px-6 py-8 text-center">
          <p className="text-lg font-semibold text-amber-200 mb-2">Zoe is warming up...</p>
          <p className="text-sm text-amber-200/60">
            No trading data yet. Once the trading engine starts scanning and placing trades, your portfolio stats will appear here.
          </p>
        </div>
      )}

      {/* Total Value */}
      <KPICard
        label="Total Value"
        value={formatCurrency(totalValue)}
        subValue={cryptoValue > 0 ? `${formatCurrency(cryptoValue)} crypto + ${formatCurrency(cashValue)} cash` : "Portfolio Value"}
        trend={allTimePnl !== 0 ? `${allTimePnl >= 0 ? '+' : ''}${formatCurrency(allTimePnl)} (${allTimePnlPct >= 0 ? '+' : ''}${allTimePnlPct.toFixed(2)}%)` : "—"}
        trendDir={allTimePnl >= 0 ? 'up' : 'down'}
        icon={DollarSign}
      />

      {/* Open Positions */}
      <PositionsTable />

      {/* Active Orders */}
      <OpenOrdersTable />

      {/* Equity Curve with Day + Overall P&L */}
      <EquityChart
        data={equityHistory}
        dailyPnl={dailyPnl}
        allTimePnl={allTimePnl}
        allTimePnlPct={allTimePnlPct}
        height={280}
      />
    </div>
  );
}
