/**
 * Zoe V4 — Supabase Client Factory
 * Provides a typed, singleton Supabase client for all V4 services.
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createLogger } from "./logger.js";

const log = createLogger("db");

let _client: SupabaseClient | null = null;

/**
 * Create a Supabase client from explicit credentials.
 * Use this in tests or when you need a non-singleton client.
 */
export function createDb(url: string, key: string): SupabaseClient {
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

/**
 * Get (or create) the singleton Supabase client from environment variables.
 */
export function getDb(): SupabaseClient {
  if (_client) return _client;

  const url = process.env["SUPABASE_URL"];
  const key = process.env["SUPABASE_SERVICE_ROLE_KEY"] || process.env["SUPABASE_KEY"];

  if (!url || !key) {
    throw new Error(
      "[DB] Missing SUPABASE_URL or SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY"
    );
  }

  _client = createDb(url, key);
  log.info("Supabase client initialized", { url });
  return _client;
}

/**
 * Reset the singleton (for testing).
 */
export function resetDb(): void {
  _client = null;
}

// ─── Typed table helpers ────────────────────────────────────────────────

export type TableName =
  | "users"
  | "accounts"
  | "trades"
  | "orders"
  | "fills"
  | "positions"
  | "daily_pnl"
  | "pnl_timeseries"
  | "option_chain_snapshots"
  | "research_items"
  | "features_daily"
  | "strategy_registry"
  | "experiment_runs"
  | "health_reports"
  | "health_events"
  | "daily_gameplans"
  | "daily_gameplan_items"
  | "audit_log"
  | "config"
  | "artifacts";

/**
 * Shorthand for db.from(table).
 * Returns a PostgrestQueryBuilder — use .select(), .insert(), etc.
 */
// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function table(name: TableName, client?: SupabaseClient): ReturnType<SupabaseClient["from"]> {
  const db = client ?? getDb();
  return db.from(name);
}

/**
 * Insert a row and return the inserted data.
 */
export async function insertRow<T extends Record<string, unknown>>(
  tableName: TableName,
  data: T,
  client?: SupabaseClient
): Promise<T & { id: string }> {
  const db = client ?? getDb();
  const { data: result, error } = await db
    .from(tableName)
    .insert(data)
    .select()
    .single();

  if (error) {
    log.error(`Insert into ${tableName} failed`, { error: error.message, data });
    throw new Error(`DB insert error (${tableName}): ${error.message}`);
  }

  return result as T & { id: string };
}

/**
 * Update rows matching a filter and return updated data.
 */
export async function updateRows<T extends Record<string, unknown>>(
  tableName: TableName,
  filter: { column: string; value: string },
  data: Partial<T>,
  client?: SupabaseClient
): Promise<T[]> {
  const db = client ?? getDb();
  const { data: result, error } = await db
    .from(tableName)
    .update(data)
    .eq(filter.column, filter.value)
    .select();

  if (error) {
    log.error(`Update ${tableName} failed`, { error: error.message, filter });
    throw new Error(`DB update error (${tableName}): ${error.message}`);
  }

  return (result ?? []) as T[];
}

/**
 * Log an audit event.
 */
export async function auditLog(
  action: string,
  details: Record<string, unknown>,
  severity: "info" | "warn" | "error" = "info",
  client?: SupabaseClient
): Promise<void> {
  try {
    const db = client ?? getDb();
    await db.from("audit_log").insert({
      actor: "zoe",
      action,
      details,
      severity,
      timestamp: new Date().toISOString(),
    });
  } catch (e) {
    log.error("Audit log write failed", { action, error: String(e) });
  }
}
