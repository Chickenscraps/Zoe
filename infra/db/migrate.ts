/**
 * Zoe V4 — Migration Runner
 * Reads SQL files from infra/db/migrations/ in order and executes them.
 * Tracks applied migrations in a _migrations table.
 *
 * Usage: npx tsx infra/db/migrate.ts
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, basename } from "node:path";
import { createClient } from "@supabase/supabase-js";

const MIGRATIONS_DIR = join(import.meta.dirname ?? ".", "migrations");

async function main() {
  const url = process.env["SUPABASE_URL"];
  const key = process.env["SUPABASE_SERVICE_ROLE_KEY"] || process.env["SUPABASE_KEY"];

  if (!url || !key) {
    console.error("❌ Set SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY");
    process.exit(1);
  }

  const db = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  // Ensure _migrations tracking table exists
  await db.rpc("exec_sql", {
    sql: `CREATE TABLE IF NOT EXISTS public._migrations (
      name TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ DEFAULT now()
    );`,
  }).then(() => {}).catch(() => {
    // RPC might not exist — try direct approach via REST
    console.warn("⚠️  exec_sql RPC not found. Run migrations manually via Supabase SQL Editor.");
    console.log("\nMigration files to run:");
  });

  // List migration files
  const files = readdirSync(MIGRATIONS_DIR)
    .filter((f) => f.endsWith(".sql"))
    .sort();

  if (files.length === 0) {
    console.log("No migration files found.");
    return;
  }

  // Check which have been applied
  const { data: applied } = await db
    .from("_migrations")
    .select("name")
    .then((r) => r)
    .catch(() => ({ data: null }));

  const appliedSet = new Set((applied ?? []).map((r: { name: string }) => r.name));

  for (const file of files) {
    if (appliedSet.has(file)) {
      console.log(`  ✅ ${file} (already applied)`);
      continue;
    }

    const sql = readFileSync(join(MIGRATIONS_DIR, file), "utf-8");
    console.log(`  🔄 Applying ${file}...`);

    try {
      // Try RPC exec
      const { error } = await db.rpc("exec_sql", { sql });
      if (error) throw error;

      // Record migration
      await db.from("_migrations").insert({ name: file });
      console.log(`  ✅ ${file} applied.`);
    } catch (e) {
      console.error(`  ❌ ${file} failed: ${e}`);
      console.log(`\n  Run manually in Supabase SQL Editor:`);
      console.log(`  File: infra/db/migrations/${file}`);
      break;
    }
  }

  console.log("\nDone.");
}

main().catch(console.error);
