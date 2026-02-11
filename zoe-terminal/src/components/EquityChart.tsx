import { ResponsiveContainer, ComposedChart, Area, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Cell } from 'recharts';
import { formatCurrency, formatDate, cn } from '../lib/utils';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface EquityDataPoint {
  date: string;
  equity: number;
  daily_pnl?: number;
}

interface EquityChartProps {
  data: EquityDataPoint[];
  height?: number;
  className?: string;
}

function EmptyState({ height }: { height: number }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4" style={{ height }}>
      <div className="relative w-24 h-16">
        <svg viewBox="0 0 96 64" className="w-full h-full">
          <path
            d="M 4 48 Q 20 44 32 36 T 60 28 T 92 16"
            fill="none"
            stroke="rgba(46, 229, 157, 0.2)"
            strokeWidth="2"
            strokeDasharray="4 4"
          />
        </svg>
      </div>
      <div className="text-center space-y-1.5">
        <p className="text-xs font-bold text-text-secondary">No trading data yet</p>
        <p className="text-[10px] text-text-muted leading-relaxed max-w-[240px]">
          P&L will appear here once Edge Factory begins paper or live trading
        </p>
      </div>
      <div className="flex items-center gap-3 mt-1">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 rounded-full bg-profit/40" />
          <span className="text-[9px] text-text-muted font-medium">Equity</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-sm bg-profit/30" />
          <span className="text-[9px] text-text-muted font-medium">Daily P&L</span>
        </div>
      </div>
    </div>
  );
}

function ChartSummary({ data }: { data: EquityDataPoint[] }) {
  if (data.length < 2) return null;

  const first = data[0].equity;
  const last = data[data.length - 1].equity;
  const totalChange = last - first;
  const totalPct = first > 0 ? (totalChange / first) * 100 : 0;
  const bestDay = Math.max(...data.map(d => d.daily_pnl ?? 0));
  const worstDay = Math.min(...data.map(d => d.daily_pnl ?? 0));
  const winDays = data.filter(d => (d.daily_pnl ?? 0) > 0).length;
  const lossDays = data.filter(d => (d.daily_pnl ?? 0) < 0).length;

  const TrendIcon = totalChange > 0 ? TrendingUp : totalChange < 0 ? TrendingDown : Minus;
  const trendColor = totalChange > 0 ? 'text-profit' : totalChange < 0 ? 'text-loss' : 'text-text-muted';

  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-bold text-text-secondary">P&L Performance</h3>
        <div className={cn("flex items-center gap-1", trendColor)}>
          <TrendIcon className="w-3.5 h-3.5" />
          <span className="text-xs font-bold tabular-nums">
            {totalChange >= 0 ? '+' : ''}{formatCurrency(totalChange)}
          </span>
          <span className="text-[10px] font-medium opacity-70">
            ({totalPct >= 0 ? '+' : ''}{totalPct.toFixed(2)}%)
          </span>
        </div>
      </div>
      <div className="flex items-center gap-4 text-[10px]">
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-profit" />
          <span className="text-text-muted font-bold">{winDays}W</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-loss" />
          <span className="text-text-muted font-bold">{lossDays}L</span>
        </div>
        {bestDay > 0 && (
          <span className="text-profit font-bold">Best: +{formatCurrency(bestDay)}</span>
        )}
        {worstDay < 0 && (
          <span className="text-loss font-bold">Worst: {formatCurrency(worstDay)}</span>
        )}
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  const equity = payload.find((p: any) => p.dataKey === 'equity');
  const dailyPnl = payload.find((p: any) => p.dataKey === 'daily_pnl');
  const pnlValue = dailyPnl?.value ?? 0;

  return (
    <div className="bg-surface border border-border-strong rounded-lg px-3 py-2.5 shadow-soft">
      <p className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1.5">
        {formatDate(label as string)}
      </p>
      {equity && (
        <div className="flex items-center justify-between gap-4">
          <span className="text-[10px] text-text-muted">Equity</span>
          <span className="text-xs font-bold text-white tabular-nums">
            {formatCurrency(equity.value)}
          </span>
        </div>
      )}
      {dailyPnl && (
        <div className="flex items-center justify-between gap-4 mt-1">
          <span className="text-[10px] text-text-muted">Daily P&L</span>
          <span className={cn(
            "text-xs font-bold tabular-nums",
            pnlValue > 0 ? "text-profit" : pnlValue < 0 ? "text-loss" : "text-text-muted"
          )}>
            {pnlValue >= 0 ? '+' : ''}{formatCurrency(pnlValue)}
          </span>
        </div>
      )}
    </div>
  );
}

export function EquityChart({ data, height = 300, className }: EquityChartProps) {
  const hasData = data.length > 1;
  const isProfit = hasData && data[data.length - 1].equity >= data[0].equity;
  const lineColor = isProfit ? "#2ee59d" : "#ff5b6e";

  // Compute Y-axis domain with padding
  const equities = hasData ? data.map(d => d.equity) : [0];
  const minEq = Math.min(...equities);
  const maxEq = Math.max(...equities);
  const eqRange = maxEq - minEq || 1;
  const yMin = minEq - eqRange * 0.1;
  const yMax = maxEq + eqRange * 0.1;

  // Max daily P&L bar height (for right axis)
  const pnls = hasData ? data.map(d => d.daily_pnl ?? 0) : [0];
  const maxAbsPnl = Math.max(Math.abs(Math.min(...pnls)), Math.abs(Math.max(...pnls)), 0.01);

  return (
    <div className={cn("w-full bg-surface border border-border rounded-lg p-5", className)}>
      {hasData ? <ChartSummary data={data} /> : (
        <div className="mb-2">
          <h3 className="text-sm font-bold text-text-secondary">P&L Performance</h3>
        </div>
      )}

      <div style={{ height }}>
        {!hasData ? (
          <EmptyState height={height} />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorEquityFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={lineColor} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={lineColor} stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical={false}
              />

              <XAxis
                dataKey="date"
                tickFormatter={(val) => {
                  const d = new Date(val);
                  return `${d.getMonth() + 1}/${d.getDate()}`;
                }}
                stroke="#52525b"
                fontSize={10}
                fontWeight={600}
                tickLine={false}
                axisLine={false}
                dy={4}
              />

              <YAxis
                yAxisId="equity"
                domain={[yMin, yMax]}
                tickFormatter={(val) => `$${val.toFixed(0)}`}
                stroke="#52525b"
                fontSize={10}
                fontWeight={600}
                tickLine={false}
                axisLine={false}
                width={52}
              />

              <YAxis
                yAxisId="pnl"
                orientation="right"
                domain={[-maxAbsPnl * 1.2, maxAbsPnl * 1.2]}
                tickFormatter={(val) => `${val >= 0 ? '+' : ''}$${val.toFixed(0)}`}
                stroke="#52525b"
                fontSize={9}
                fontWeight={600}
                tickLine={false}
                axisLine={false}
                width={46}
              />

              <ReferenceLine
                yAxisId="pnl"
                y={0}
                stroke="rgba(255,255,255,0.08)"
                strokeDasharray="2 2"
              />

              <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }} />

              <Bar
                yAxisId="pnl"
                dataKey="daily_pnl"
                barSize={data.length > 30 ? 4 : data.length > 14 ? 8 : 14}
                radius={[2, 2, 0, 0]}
                opacity={0.5}
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={(entry.daily_pnl ?? 0) >= 0 ? "#2ee59d" : "#ff5b6e"}
                    opacity={0.35}
                  />
                ))}
              </Bar>

              <Area
                yAxisId="equity"
                type="monotone"
                dataKey="equity"
                stroke={lineColor}
                fillOpacity={1}
                fill="url(#colorEquityFill)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: lineColor, stroke: '#0b0c0f', strokeWidth: 2 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {hasData && (
        <div className="flex items-center justify-center gap-6 mt-3 pt-3 border-t border-border/50">
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 rounded-full" style={{ backgroundColor: lineColor }} />
            <span className="text-[9px] text-text-muted font-bold uppercase tracking-wider">Equity Curve</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm bg-profit/40" />
            <span className="text-[9px] text-text-muted font-bold uppercase tracking-wider">Profit Day</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm bg-loss/40" />
            <span className="text-[9px] text-text-muted font-bold uppercase tracking-wider">Loss Day</span>
          </div>
        </div>
      )}
    </div>
  );
}
