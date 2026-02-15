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
          <h2 className="font-pixel text-[0.55rem] uppercase tracking-[0.08em] text-earth-700">Recent Orders</h2>
          <div className="text-sm text-text-secondary">
            {cryptoOrders.length} orders
          </div>
        </div>
        <div className="bg-paper-100/80 border-2 border-earth-700/10 overflow-hidden">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead>
              <tr className="border-b border-earth-700/10 font-pixel text-[0.35rem] font-black uppercase tracking-widest text-text-muted">
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
                <tr><td colSpan={7} className="px-4 py-6 text-center"><span className="font-pixel text-[0.4rem] text-text-muted uppercase tracking-[0.15em]">None</span></td></tr>
              ) : (
                cryptoOrders.map((order) => (
                  <tr key={order.id} className="border-b border-earth-700/8 hover:bg-sakura-500/5 transition-colors">
                    <td className="px-4 py-3 font-semibold text-earth-700">{order.symbol}</td>
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
                      <span className={`uppercase text-[10px] font-bold px-2 py-0.5 ${
                        order.status === 'filled' ? 'bg-profit/15 text-profit' :
                        order.status === 'submitted' || order.status === 'new' ? 'bg-yellow-500/15 text-yellow-400' :
                        order.status === 'canceled' || order.status === 'rejected' ? 'bg-loss/15 text-loss' :
                        'bg-earth-700/5 text-text-muted'
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
          <h2 className="font-pixel text-[0.55rem] uppercase tracking-[0.08em] text-earth-700">Fill History</h2>
          <div className="text-sm text-text-secondary">
            {cryptoFills.length} fills
          </div>
        </div>
        <div className="bg-paper-100/80 border-2 border-earth-700/10 overflow-hidden">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead>
              <tr className="border-b border-earth-700/10 font-pixel text-[0.35rem] font-black uppercase tracking-widest text-text-muted">
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
                <tr><td colSpan={7} className="px-4 py-6 text-center"><span className="font-pixel text-[0.4rem] text-text-muted uppercase tracking-[0.15em]">None</span></td></tr>
              ) : (
                cryptoFills.map((fill) => {
                  const notional = fill.qty * fill.price;
                  return (
                    <tr key={fill.id} className="border-b border-earth-700/8 hover:bg-sakura-500/5 transition-colors">
                      <td className="px-4 py-3 font-semibold text-earth-700">{fill.symbol}</td>
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
