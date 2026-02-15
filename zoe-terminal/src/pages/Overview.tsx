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

  return (
    <div className="space-y-8">
      {/* Alert Banners */}
      <AlertBanner />

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
