import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { formatCurrency, formatDate, cn } from '../lib/utils';

interface EquityChartProps {
  data: { date: string; equity: number }[];
  height?: number;
  className?: string;
}

export function EquityChart({ data, height = 300, className }: EquityChartProps) {
  const isProfit = data.length > 1 && data[data.length - 1].equity >= data[0].equity;
  const color = isProfit ? "#22c55e" : "#ef4444"; // brand-profit or brand-loss

  return (
    <div className={cn("w-full bg-surface border border-border rounded-lg p-4", className)}>
      <div className="mb-4">
        <h3 className="text-sm font-medium text-text-secondary">Equity Curve</h3>
      </div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.2}/>
                <stop offset="95%" stopColor={color} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis 
              dataKey="date" 
              tickFormatter={(val) => formatDate(val).split(',')[0]}
              stroke="#71717a"
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <YAxis 
              domain={['auto', 'auto']}
              tickFormatter={(val) => formatCurrency(val).split('.')[0]}
              stroke="#71717a"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={60}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#1e1e1e', borderColor: '#333' }}
              itemStyle={{ color: '#e5e7eb' }}
              formatter={(value: any) => [formatCurrency(value), 'Equity']}
              labelFormatter={(label) => formatDate(label as string)}
            />
            <Area 
              type="monotone" 
              dataKey="equity" 
              stroke={color} 
              fillOpacity={1} 
              fill="url(#colorEquity)" 
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
