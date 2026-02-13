import { useMemo, useState } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { formatCurrency, cn } from '../lib/utils';
import type { EquityPoint } from '../hooks/useDashboardData';

interface EquityChartProps {
  data: EquityPoint[];
  dailyPnl: number;
  allTimePnl: number;
  allTimePnlPct: number;
  height?: number;
  className?: string;
}

type ChartView = 'today' | '7d' | 'alltime';

/** Format a timestamp for the X-axis depending on zoom level */
function formatXTick(val: string, view: ChartView) {
  const d = new Date(val);
  if (isNaN(d.getTime())) return val;
  if (view === 'today') {
    // Show HH:MM
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  }
  if (view === '7d') {
    // Show day + time
    return `${d.getMonth() + 1}/${d.getDate()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}`;
  }
  // All time — show M/D
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/** Format tooltip label with full date+time */
function formatTooltipLabel(val: string) {
  const d = new Date(val);
  if (isNaN(d.getTime())) return val;
  return d.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export function EquityChart({ data, dailyPnl, allTimePnl, allTimePnlPct, height = 300, className }: EquityChartProps) {
  const [view, setView] = useState<ChartView>('alltime');
  const hasData = data.length > 1;

  // Filter data based on view
  const filteredData = useMemo(() => {
    if (!hasData) return [];
    if (view === 'today') {
      const today = new Date().toISOString().slice(0, 10);
      const todayData = data.filter(p => p.date.startsWith(today));
      return todayData.length > 0 ? todayData : data.slice(-1);
    }
    if (view === '7d') {
      const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
      const weekData = data.filter(p => p.date >= cutoff);
      return weekData.length > 0 ? weekData : data.slice(-1);
    }
    return data;
  }, [data, hasData, view]);

  const isProfit = view === 'today' ? dailyPnl >= 0 : allTimePnl >= 0;
  const color = isProfit ? "#2ee59d" : "#ff5b6e";

  // Convert to P&L data (delta from first point in view)
  const pnlData = useMemo(() => {
    if (filteredData.length === 0) return [];
    const base = filteredData[0].equity;
    return filteredData.map(point => ({
      date: point.date,
      equity: point.equity,
      pnl: point.equity - base,
    }));
  }, [filteredData]);

  const displayPnl = view === 'today' ? dailyPnl : allTimePnl;
  const displayPct = view === 'today' ? 0 : allTimePnlPct;

  // Determine how many ticks to show based on data density
  const tickCount = useMemo(() => {
    const len = pnlData.length;
    if (len < 10) return len;
    if (len < 50) return 6;
    return 8;
  }, [pnlData.length]);

  return (
    <div className={cn("card-premium card-shimmer-sweep p-4 sm:p-6", className)}>
      {/* Header with toggle */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4 sm:mb-6">
        <div>
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-2">
            P&L Curve
          </h3>
          {/* P&L Summary */}
          <div className="flex items-baseline gap-3">
            <span className={cn(
              "text-xl sm:text-2xl font-black font-mono tabular-nums",
              isProfit ? "text-profit" : "text-loss"
            )}>
              {displayPnl >= 0 ? '+' : ''}{formatCurrency(displayPnl)}
            </span>
            {view === 'alltime' && allTimePnlPct !== 0 && (
              <span className={cn(
                "text-xs font-bold tabular-nums",
                isProfit ? "text-profit/70" : "text-loss/70"
              )}>
                {displayPct >= 0 ? '+' : ''}{displayPct.toFixed(2)}%
              </span>
            )}
            <span className="text-[10px] text-text-dim uppercase tracking-widest font-bold">
              {view === 'today' ? "Today" : view === '7d' ? "7 Days" : "All Time"}
            </span>
          </div>
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-0 bg-surface-base border border-border rounded-full p-0.5">
          {(['today', '7d', 'alltime'] as ChartView[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={cn(
                "px-3 py-1 rounded-full text-[9px] font-black tracking-widest uppercase transition-all",
                view === v
                  ? "bg-text-primary text-background"
                  : "text-text-muted hover:text-text-primary"
              )}
            >
              {v === 'today' ? '1D' : v === '7d' ? '7D' : 'All'}
            </button>
          ))}
        </div>
      </div>

      {!hasData ? (
        <div
          className="flex items-center justify-center border border-dashed border-border rounded-lg"
          style={{ height }}
        >
          <div className="text-center">
            <p className="text-text-muted text-xs font-bold">No equity data yet</p>
            <p className="text-text-muted/60 text-[10px] mt-1">
              Data will appear once cash snapshots are recorded
            </p>
          </div>
        </div>
      ) : (
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={pnlData}>
              <defs>
                <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.2} />
                  <stop offset="50%" stopColor={color} stopOpacity={0.05} />
                  <stop offset="95%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tickFormatter={(val) => formatXTick(val, view)}
                stroke="rgba(255,255,255,0.2)"
                fontSize={9}
                tickLine={false}
                axisLine={false}
                dy={8}
                interval="preserveStartEnd"
                minTickGap={40}
              />
              <YAxis
                domain={['auto', 'auto']}
                tickFormatter={(val: number) => {
                  const prefix = val >= 0 ? '+' : '';
                  return `${prefix}$${Math.abs(val).toFixed(0)}`;
                }}
                stroke="rgba(255,255,255,0.2)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                width={65}
              />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#141823',
                  borderColor: 'rgba(255,255,255,0.08)',
                  borderRadius: '12px',
                  padding: '10px 14px',
                  fontSize: '11px',
                }}
                itemStyle={{ color: '#f3f4f6' }}
                formatter={(value: number, name: string) => {
                  if (name === 'pnl') {
                    const prefix = value >= 0 ? '+' : '';
                    return [`${prefix}${formatCurrency(value)}`, 'P&L'];
                  }
                  return [formatCurrency(value), 'Total Value'];
                }}
                labelFormatter={(label) => formatTooltipLabel(label as string)}
              />
              <Area
                type="monotone"
                dataKey="pnl"
                stroke={color}
                fillOpacity={1}
                fill="url(#colorEquity)"
                strokeWidth={2}
                dot={false}
                animationDuration={800}
                animationEasing="ease-out"
                activeDot={{
                  r: 4,
                  stroke: color,
                  strokeWidth: 2,
                  fill: '#141823',
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
