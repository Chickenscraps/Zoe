import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, CheckCircle, Clock, Lock, RefreshCw, Shield, Zap } from "lucide-react";
import { supabase } from "../lib/supabaseClient";
import { useModeContext } from "../lib/mode";
import { cn } from "../lib/utils";
import type { Database } from "../lib/types";

type HealthHeartbeat = Database["public"]["Tables"]["health_heartbeat"]["Row"];
type OrderIntent = Database["public"]["Tables"]["order_intents"]["Row"];
type TradeLock = Database["public"]["Tables"]["trade_locks"]["Row"];
type ReconcileEvent = Database["public"]["Tables"]["crypto_reconciliation_events"]["Row"];

export default function Ops() {
  const { mode } = useModeContext();
  const [heartbeats, setHeartbeats] = useState<HealthHeartbeat[]>([]);
  const [activeIntents, setActiveIntents] = useState<OrderIntent[]>([]);
  const [tradeLocks, setTradeLocks] = useState<TradeLock[]>([]);
  const [recentRecon, setRecentRecon] = useState<ReconcileEvent | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const [hbRes, intentRes, lockRes, reconRes] = await Promise.all([
      supabase.from("health_heartbeat").select("*").eq("mode", mode),
      supabase
        .from("order_intents")
        .select("*")
        .eq("mode", mode)
        .not("status", "in", "(filled,cancelled,replaced,rejected,expired)")
        .order("created_at", { ascending: false })
        .limit(20),
      supabase.from("trade_locks").select("*").eq("mode", mode),
      supabase
        .from("crypto_reconciliation_events")
        .select("*")
        .eq("mode", mode)
        .order("taken_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
    ]);

    setHeartbeats((hbRes.data ?? []) as HealthHeartbeat[]);
    setActiveIntents((intentRes.data ?? []) as OrderIntent[]);
    setTradeLocks((lockRes.data ?? []) as TradeLock[]);
    setRecentRecon((reconRes.data ?? null) as ReconcileEvent | null);
    setLoading(false);
  }, [mode]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const systemStatus = useMemo(() => {
    const safeModeHb = heartbeats.find(h => h.component === "safe_mode");
    if (safeModeHb?.status === "degraded") return "SAFE_MODE";
    const degraded = heartbeats.filter(h => h.status === "degraded");
    if (degraded.length > 0) return "DEGRADED";
    if (heartbeats.length === 0) return "UNKNOWN";
    return "HEALTHY";
  }, [heartbeats]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-surface-card rounded w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <div key={i} className="h-32 bg-surface-card rounded" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* System Status Banner */}
      <div className={cn(
        "rounded-lg border p-4 flex items-center gap-3",
        systemStatus === "HEALTHY" && "border-profit/30 bg-profit/5",
        systemStatus === "DEGRADED" && "border-yellow-500/30 bg-yellow-500/5",
        systemStatus === "SAFE_MODE" && "border-loss/30 bg-loss/5",
        systemStatus === "UNKNOWN" && "border-border bg-surface-card",
      )}>
        {systemStatus === "HEALTHY" && <CheckCircle className="w-5 h-5 text-profit" />}
        {systemStatus === "DEGRADED" && <AlertTriangle className="w-5 h-5 text-yellow-500" />}
        {systemStatus === "SAFE_MODE" && <Shield className="w-5 h-5 text-loss" />}
        {systemStatus === "UNKNOWN" && <Activity className="w-5 h-5 text-text-muted" />}
        <div>
          <div className="text-sm font-semibold text-text-primary">
            System: {systemStatus}
          </div>
          <div className="text-xs text-text-muted">
            Mode: {mode} | {heartbeats.length} components reporting
          </div>
        </div>
        <div className="ml-auto text-xs text-text-dim">
          {new Date().toLocaleTimeString([], { hour12: false })}
        </div>
      </div>

      {/* Component Health */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-3 flex items-center gap-2">
          <Zap className="w-3 h-3" /> Component Health
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {heartbeats.map(hb => (
            <div key={hb.component} className="rounded-lg border border-border bg-surface-card p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-text-primary">{hb.component}</span>
                <span className={cn(
                  "text-[10px] font-bold uppercase px-1.5 py-0.5 rounded",
                  hb.status === "ok" && "bg-profit/10 text-profit",
                  hb.status === "degraded" && "bg-loss/10 text-loss",
                )}>
                  {hb.status}
                </span>
              </div>
              <div className="text-[10px] text-text-muted truncate">{hb.message || "—"}</div>
              <div className="text-[9px] text-text-dim mt-1">
                <Clock className="w-2.5 h-2.5 inline mr-0.5" />
                {hb.updated_at ? new Date(hb.updated_at).toLocaleTimeString([], { hour12: false }) : "—"}
              </div>
            </div>
          ))}
          {heartbeats.length === 0 && (
            <div className="col-span-full text-xs text-text-muted p-4 text-center">
              No component heartbeats. Start services to see health data.
            </div>
          )}
        </div>
      </section>

      {/* Active Order Intents */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-3 flex items-center gap-2">
          <RefreshCw className="w-3 h-3" /> Active Order Intents ({activeIntents.length})
        </h3>
        {activeIntents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th className="text-left py-2 px-2">Symbol</th>
                  <th className="text-left py-2 px-2">Side</th>
                  <th className="text-left py-2 px-2">Type</th>
                  <th className="text-right py-2 px-2">Limit</th>
                  <th className="text-right py-2 px-2">Qty</th>
                  <th className="text-left py-2 px-2">Status</th>
                  <th className="text-left py-2 px-2">Engine</th>
                  <th className="text-left py-2 px-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {activeIntents.map(intent => (
                  <tr key={intent.id} className="border-b border-border/50 hover:bg-white/[0.02]">
                    <td className="py-1.5 px-2 font-mono font-semibold text-text-primary">
                      {intent.symbol.replace("-USD", "")}
                    </td>
                    <td className={cn("py-1.5 px-2 font-semibold", intent.side === "buy" ? "text-profit" : "text-loss")}>
                      {intent.side.toUpperCase()}
                    </td>
                    <td className="py-1.5 px-2 text-text-muted">{intent.order_type}</td>
                    <td className="py-1.5 px-2 text-right font-mono text-text-primary">
                      {intent.limit_price ? `$${Number(intent.limit_price).toFixed(2)}` : "—"}
                    </td>
                    <td className="py-1.5 px-2 text-right font-mono text-text-primary">
                      {intent.qty ? Number(intent.qty).toFixed(6) : "—"}
                    </td>
                    <td className="py-1.5 px-2">
                      <span className={cn(
                        "text-[10px] font-bold uppercase px-1.5 py-0.5 rounded",
                        intent.status === "submitted" && "bg-blue-500/10 text-blue-400",
                        intent.status === "acked" && "bg-profit/10 text-profit",
                        intent.status === "partial_fill" && "bg-yellow-500/10 text-yellow-500",
                        intent.status === "error" && "bg-loss/10 text-loss",
                      )}>
                        {intent.status}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-text-muted">{intent.engine || "—"}</td>
                    <td className="py-1.5 px-2 text-text-dim">
                      {new Date(intent.created_at).toLocaleTimeString([], { hour12: false })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-text-muted p-4 text-center border border-border/50 rounded-lg">
            No active order intents.
          </div>
        )}
      </section>

      {/* Trade Locks */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-3 flex items-center gap-2">
          <Lock className="w-3 h-3" /> Trade Locks ({tradeLocks.length})
        </h3>
        {tradeLocks.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {tradeLocks.map(lock => (
              <div key={`${lock.symbol}-${lock.engine}`} className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-text-primary">{lock.symbol}</span>
                  <Lock className="w-3 h-3 text-yellow-500" />
                </div>
                <div className="text-[10px] text-text-muted">Engine: {lock.engine}</div>
                <div className="text-[10px] text-text-dim">
                  Locked: {new Date(lock.locked_at).toLocaleTimeString([], { hour12: false })}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-muted p-4 text-center border border-border/50 rounded-lg">
            No active trade locks.
          </div>
        )}
      </section>

      {/* Latest Reconciliation */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-3 flex items-center gap-2">
          <Activity className="w-3 h-3" /> Latest Reconciliation
        </h3>
        {recentRecon ? (
          <div className={cn(
            "rounded-lg border p-4",
            recentRecon.status === "ok" ? "border-profit/20 bg-profit/5" : "border-loss/20 bg-loss/5",
          )}>
            <div className="flex items-center gap-2 mb-2">
              {recentRecon.status === "ok" ? (
                <CheckCircle className="w-4 h-4 text-profit" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-loss" />
              )}
              <span className="text-sm font-semibold text-text-primary uppercase">{recentRecon.status}</span>
              <span className="text-xs text-text-muted ml-auto">
                {new Date(recentRecon.taken_at).toLocaleString()}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-text-muted">Exchange Cash:</span>
                <span className="ml-2 font-mono text-text-primary">${Number(recentRecon.rh_cash).toFixed(2)}</span>
              </div>
              <div>
                <span className="text-text-muted">DB Cash:</span>
                <span className="ml-2 font-mono text-text-primary">${Number(recentRecon.local_cash).toFixed(2)}</span>
              </div>
              <div>
                <span className="text-text-muted">Cash Diff:</span>
                <span className={cn(
                  "ml-2 font-mono",
                  Number(recentRecon.cash_diff) > 0.01 ? "text-loss" : "text-profit",
                )}>
                  ${Number(recentRecon.cash_diff).toFixed(2)}
                </span>
              </div>
            </div>
            {recentRecon.reason && (
              <div className="mt-2 text-[10px] text-text-muted">{recentRecon.reason}</div>
            )}
          </div>
        ) : (
          <div className="text-xs text-text-muted p-4 text-center border border-border/50 rounded-lg">
            No reconciliation events. Start a trading service to see reconciliation data.
          </div>
        )}
      </section>
    </div>
  );
}
