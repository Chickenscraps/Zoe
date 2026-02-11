import { Activity, Database as DbIcon, Shield, Wifi } from "lucide-react";
import { StatusChip } from "../components/StatusChip";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatCurrency } from "../lib/utils";

export default function Health() {
  const { healthSummary, dailyNotional, cryptoOrders, loading } = useDashboardData();

  const services = [
    {
      name: "Robinhood Crypto API",
      status: healthSummary.status === "LIVE" ? "ok" : "error",
      icon: Wifi,
    },
    {
      name: "Reconciliation Engine",
      status: healthSummary.status === "LIVE" ? "ok" : "warning",
      icon: Shield,
    },
    { name: "Snapshot Store", status: "ok", icon: DbIcon },
    { name: "Discord Control", status: "ok", icon: Activity },
  ];

  if (loading)
    return <div className="text-text-secondary animate-pulse">Loading health telemetry...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-white">Crypto Health</h2>
        <StatusChip
          status={healthSummary.status === "LIVE" ? "ok" : "error"}
          label={healthSummary.status}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {services.map((service, i) => {
          const Icon = service.icon;
          return (
            <div key={i} className="bg-surface border border-border rounded-lg p-5">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-surface-highlight rounded-lg text-text-secondary">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-sm">{service.name}</h3>
                  </div>
                </div>
                <StatusChip status={service.status as never} label={service.status.toUpperCase()} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-surface border border-border rounded-lg p-6 space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-text-secondary">Last reconcile</span>
          <span className="text-white">{healthSummary.lastReconcile ?? "never"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Mismatch reason</span>
          <span className="text-white">{healthSummary.reason}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Open orders</span>
          <span className="text-white">
            {
              cryptoOrders.filter((o) => ["submitted", "partially_filled"].includes(o.status))
                .length
            }
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Daily notional used</span>
          <span className="text-white">{formatCurrency(dailyNotional?.amount ?? 0)}</span>
        </div>
      </div>
    </div>
  );
}
