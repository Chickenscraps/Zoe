import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { formatCurrency, formatDate, cn } from '../lib/utils';
import type { EquityPoint } from '../hooks/useDashboardData';

interface EquityChartProps {
  data: EquityPoint[];
  height?: number;
  className?: string;
}

export function EquityChart({ data, height = 300, className }: EquityChartProps) {
  const hasData = data.length > 1;
  const isProfit = hasData && data[data.length - 1].equity >= data[0].equity;
  const color = isProfit ? "#2ee59d" : "#ff5b6e"; // profit or loss from design system

  // Summary stats
  const startEquity = hasData ? data[0].equity : 0;
  const endEquity = hasData ? data[data.length - 1].equity : 0;
  const totalChange = endEquity - startEquity;
  const totalChangePct = startEquity > 0 ? (totalChange / startEquity) * 100 : 0;

  return (
    <div className={cn("card-premium p-8", className)}>
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted">
          Equity Curve
        </h3>
        {hasData && (
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-text-secondary">
              {formatCurrency(endEquity)}
            </span>
            <span
              className={cn(
                "text-[10px] font-black font-mono px-2 py-0.5 rounded-full",
                isProfit
                  ? "bg-profit/10 text-profit"
                  : "bg-loss/10 text-loss"
              )}
            >
              {totalChange >= 0 ? "+" : ""}
              {formatCurrency(totalChange)} ({totalChangePct >= 0 ? "+" : ""}
              {totalChangePct.toFixed(2)}%)
            </span>
          </div>
        )}
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
            <AreaChart data={data}>
              <defs>
                <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.15} />
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
                tickFormatter={(val) => {
                  const d = new Date(val);
                  return `${d.getMonth() + 1}/${d.getDate()}`;
                }}
                stroke="rgba(255,255,255,0.2)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                dy={8}
              />
              <YAxis
                domain={['auto', 'auto']}
                tickFormatter={(val) => formatCurrency(val).split('.')[0]}
                stroke="rgba(255,255,255,0.2)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                width={65}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#141823',
                  borderColor: 'rgba(255,255,255,0.08)',
                  borderRadius: '12px',
                  padding: '10px 14px',
                  fontSize: '11px',
                }}
                itemStyle={{ color: '#f3f4f6' }}
                formatter={(value: number) => [formatCurrency(value), 'Equity']}
                labelFormatter={(label) => formatDate(label as string)}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke={color}
                fillOpacity={1}
                fill="url(#colorEquity)"
                strokeWidth={2}
                dot={false}
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
