import { supabase } from "./supabase";
import type {
  Position,
  Signal,
  Regime,
  EfState,
  CashSnapshot,
  PnlDaily,
  HealthHeartbeat,
  ZoeEvent,
} from "./types";

export async function fetchPositions(): Promise<Position[]> {
  const { data, error } = await supabase
    .from("ef_positions")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(50);
  if (error) console.error("ef_positions:", error);
  return (data as Position[]) ?? [];
}

export async function fetchSignals(): Promise<Signal[]> {
  const { data, error } = await supabase
    .from("ef_signals")
    .select("*")
    .order("generated_at", { ascending: false })
    .limit(30);
  if (error) console.error("ef_signals:", error);
  return (data as Signal[]) ?? [];
}

export async function fetchLatestRegime(): Promise<Regime | null> {
  const { data, error } = await supabase
    .from("ef_regimes")
    .select("*")
    .order("detected_at", { ascending: false })
    .limit(1)
    .single();
  if (error && error.code !== "PGRST116") console.error("ef_regimes:", error);
  return (data as Regime) ?? null;
}

export async function fetchState(): Promise<EfState[]> {
  const { data, error } = await supabase.from("ef_state").select("*");
  if (error) console.error("ef_state:", error);
  return (data as EfState[]) ?? [];
}

export async function fetchCashSnapshots(): Promise<CashSnapshot[]> {
  const { data, error } = await supabase
    .from("crypto_cash_snapshots")
    .select("*")
    .order("taken_at", { ascending: false })
    .limit(100);
  if (error) console.error("crypto_cash_snapshots:", error);
  return (data as CashSnapshot[]) ?? [];
}

export async function fetchPnlDaily(): Promise<PnlDaily[]> {
  const { data, error } = await supabase
    .from("pnl_daily")
    .select("*")
    .order("date", { ascending: false })
    .limit(30);
  if (error) console.error("pnl_daily:", error);
  return (data as PnlDaily[]) ?? [];
}

export async function fetchHeartbeats(): Promise<HealthHeartbeat[]> {
  const { data, error } = await supabase
    .from("health_heartbeat")
    .select("*")
    .order("last_heartbeat", { ascending: false })
    .limit(10);
  if (error) console.error("health_heartbeat:", error);
  return (data as HealthHeartbeat[]) ?? [];
}

export async function fetchRecentEvents(): Promise<ZoeEvent[]> {
  const { data, error } = await supabase
    .from("zoe_events")
    .select("*")
    .order("ts", { ascending: false })
    .limit(30);
  if (error) console.error("zoe_events:", error);
  return (data as ZoeEvent[]) ?? [];
}
