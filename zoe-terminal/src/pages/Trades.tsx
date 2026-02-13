import { useDashboardData } from '../hooks/useDashboardData';
import { PositionsTable } from '../components/PositionsTable';
import { formatCurrency, formatDate } from '../lib/utils';

export default function Trades() {
  const { cryptoOrders, cryptoFills, loading } = useDashboardData();

  if (loading) return <div className="text-text-secondary animate-pulse">Loading trades...</div>;

  return (
    <div className="space-y-8">
      {/* Open Positions */}
      <PositionsTable />

      {/* Recent Orders */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-white">Recent Orders</h2>
          <div className="text-sm text-text-secondary">
            {cryptoOrders.length} orders
          </div>
        </div>
        <div className="card-premium overflow-hidden">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead>
              <tr className="border-b border-border text-[10px] font-black uppercase tracking-widest text-text-muted">
                <th className="px-3 sm:px-4 py-3 text-left">Symbol</th>
                <th className="px-3 sm:px-4 py-3 text-left">Side</th>
                <th className="px-3 sm:px-4 py-3 text-left">Type</th>
                <th className="px-3 sm:px-4 py-3 text-right">Qty</th>
                <th className="px-3 sm:px-4 py-3 text-right">Notional</th>
                <th className="px-3 sm:px-4 py-3 text-left">Status</th>
                <th className="px-3 sm:px-4 py-3 text-left">Time</th>
              </tr>
            </thead>
            <tbody>
              {cryptoOrders.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-text-muted italic">No orders yet</td></tr>
              ) : (
                cryptoOrders.map((order) => (
                  <tr key={order.id} className="border-b border-border/50 hover:bg-surface-highlight/30 transition-colors">
                    <td className="px-4 py-3 font-semibold text-white">{order.symbol}</td>
                    <td className="px-4 py-3">
                      <span className={`uppercase text-xs font-bold ${order.side === 'buy' ? 'text-profit' : 'text-loss'}`}>
                        {order.side}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{order.order_type}</td>
                    <td className="px-4 py-3 text-right font-mono text-text-primary">
                      {order.qty ? Number(order.qty).toFixed(8) : '-'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-text-primary">
                      {order.notional ? formatCurrency(order.notional) : '-'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`uppercase text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        order.status === 'filled' ? 'bg-profit/15 text-profit' :
                        order.status === 'submitted' || order.status === 'open' ? 'bg-yellow-500/15 text-yellow-400' :
                        order.status === 'canceled' || order.status === 'rejected' || order.status === 'failed' ? 'bg-loss/15 text-loss' :
                        'bg-white/10 text-text-muted'
                      }`}>
                        {order.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-text-secondary text-xs">
                      {order.requested_at ? formatDate(order.requested_at) : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          </div>
        </div>
      </div>

      {/* Fill History */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-white">Fill History</h2>
          <div className="text-sm text-text-secondary">
            {cryptoFills.length} fills
          </div>
        </div>
        <div className="card-premium overflow-hidden">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead>
              <tr className="border-b border-border text-[10px] font-black uppercase tracking-widest text-text-muted">
                <th className="px-3 sm:px-4 py-3 text-left">Symbol</th>
                <th className="px-3 sm:px-4 py-3 text-left">Side</th>
                <th className="px-3 sm:px-4 py-3 text-right">Qty</th>
                <th className="px-3 sm:px-4 py-3 text-right">Price</th>
                <th className="px-3 sm:px-4 py-3 text-right">Notional</th>
                <th className="px-3 sm:px-4 py-3 text-right">Fee</th>
                <th className="px-3 sm:px-4 py-3 text-left">Executed</th>
              </tr>
            </thead>
            <tbody>
              {cryptoFills.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-text-muted italic">No fills yet</td></tr>
              ) : (
                cryptoFills.map((fill) => {
                  const notional = fill.qty * fill.price;
                  return (
                    <tr key={fill.id} className="border-b border-border/50 hover:bg-surface-highlight/30 transition-colors">
                      <td className="px-4 py-3 font-semibold text-white">{fill.symbol}</td>
                      <td className="px-4 py-3">
                        <span className={`uppercase text-xs font-bold ${fill.side === 'buy' ? 'text-profit' : 'text-loss'}`}>
                          {fill.side}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-text-primary">
                        {Number(fill.qty).toFixed(8)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-text-primary">
                        {formatCurrency(fill.price)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-text-primary">
                        {formatCurrency(notional)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-text-muted">
                        {formatCurrency(fill.fee)}
                      </td>
                      <td className="px-4 py-3 text-text-secondary text-xs">
                        {fill.executed_at ? formatDate(fill.executed_at) : '-'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          </div>
        </div>
      </div>
    </div>
  );
}
