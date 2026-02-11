import { useDashboardData } from "../hooks/useDashboardData";
import { formatCurrency, formatDate } from "../lib/utils";

export default function Trades() {
  const { cryptoOrders, cryptoFills, loading } = useDashboardData();

  if (loading)
    return <div className="text-text-secondary animate-pulse">Loading crypto blotter...</div>;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">Crypto Trade Blotter</h2>
        <div className="text-sm text-text-secondary">{cryptoOrders.length} recent orders</div>
      </div>

      <div className="card-premium p-6">
        <h3 className="text-xs font-black uppercase tracking-[0.16em] text-text-muted mb-4">
          Orders
        </h3>
        <div className="space-y-2">
          {cryptoOrders.length > 0 ? (
            cryptoOrders.map((order) => (
              <div
                key={order.id}
                className="grid grid-cols-6 gap-2 text-xs border-b border-border/40 py-2"
              >
                <span className="font-bold text-white">{order.symbol}</span>
                <span className={order.side === "buy" ? "text-profit" : "text-loss"}>
                  {order.side.toUpperCase()}
                </span>
                <span className="text-text-secondary">{order.order_type}</span>
                <span className="text-text-secondary">{formatCurrency(order.notional ?? 0)}</span>
                <span className="text-text-muted uppercase">{order.status}</span>
                <span className="text-text-dim">{formatDate(order.requested_at)}</span>
              </div>
            ))
          ) : (
            <div className="text-xs italic text-text-dim">No orders yet.</div>
          )}
        </div>
      </div>

      <div className="card-premium p-6">
        <h3 className="text-xs font-black uppercase tracking-[0.16em] text-text-muted mb-4">
          Fills
        </h3>
        <div className="space-y-2">
          {cryptoFills.length > 0 ? (
            cryptoFills.map((fill) => (
              <div
                key={fill.id}
                className="grid grid-cols-6 gap-2 text-xs border-b border-border/40 py-2"
              >
                <span className="font-bold text-white">{fill.symbol}</span>
                <span className={fill.side === "buy" ? "text-profit" : "text-loss"}>
                  {fill.side.toUpperCase()}
                </span>
                <span className="text-text-secondary">qty {fill.qty}</span>
                <span className="text-text-secondary">px {formatCurrency(fill.price)}</span>
                <span className="text-text-muted">fee {formatCurrency(fill.fee)}</span>
                <span className="text-text-dim">{formatDate(fill.executed_at)}</span>
              </div>
            ))
          ) : (
            <div className="text-xs italic text-text-dim">No fills yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
