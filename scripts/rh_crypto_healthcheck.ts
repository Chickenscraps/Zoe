#!/usr/bin/env -S node --import tsx
/**
 * Robinhood Crypto API Health Check
 *
 * Usage:
 *   npx tsx scripts/rh_crypto_healthcheck.ts
 *
 * Reads .env.secrets for credentials, calls a safe GET endpoint,
 * and prints PASS/FAIL with status and response keys (no PII).
 *
 * Optionally writes result to Supabase health_heartbeat table
 * if VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are set.
 */

import { isConfigured, probeHealth, type RhHealthResult } from "../src/integrations/robinhood_crypto_client.js";
import { existsSync, readFileSync, appendFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";

// ---------------------------------------------------------------------------
// Load .env.secrets if present
// ---------------------------------------------------------------------------

function loadEnvFile(path: string) {
  if (!existsSync(path)) return;
  const lines = readFileSync(path, "utf-8").split("\n");
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eqIdx = line.indexOf("=");
    if (eqIdx === -1) continue;
    const key = line.slice(0, eqIdx).trim();
    let value = line.slice(eqIdx + 1).trim();
    // Strip surrounding quotes
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) {
      process.env[key] = value;
    }
  }
}

const rootDir = resolve(dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1")), "..");
loadEnvFile(resolve(rootDir, ".env.secrets"));
loadEnvFile(resolve(rootDir, ".env"));

// ---------------------------------------------------------------------------
// Run health check
// ---------------------------------------------------------------------------

async function main() {
  console.log("=== Robinhood Crypto API Health Check ===\n");

  if (!isConfigured()) {
    console.log("SKIP  | RH_CRYPTO_API_KEY / RH_CRYPTO_PRIVATE_KEY_SEED not set");
    console.log("      | Set credentials in .env.secrets to enable this check.");
    await writeResult({ ok: false, status: 0, latencyMs: 0, error: "Not configured" });
    process.exit(0);
  }

  const result = await probeHealth();

  if (result.ok) {
    console.log(`PASS  | HTTP ${result.status} | ${result.latencyMs}ms`);
    if (result.responseKeys) {
      console.log(`      | Response keys: ${result.responseKeys.join(", ")}`);
    }
  } else {
    console.log(`FAIL  | HTTP ${result.status} | ${result.latencyMs}ms`);
    console.log(`      | Error: ${result.error}`);
  }

  await writeResult(result);
  process.exit(result.ok ? 0 : 1);
}

// ---------------------------------------------------------------------------
// Persist result (Supabase or local log)
// ---------------------------------------------------------------------------

async function writeResult(result: RhHealthResult) {
  const supabaseUrl = process.env.VITE_SUPABASE_URL || process.env.SUPABASE_URL;
  const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;

  if (supabaseUrl && supabaseKey) {
    try {
      const payload = {
        instance_id: process.env.ZOE_INSTANCE_ID || "default",
        component: "robinhood_crypto",
        status: result.ok ? "ok" : "error",
        last_heartbeat: new Date().toISOString(),
        details: {
          http_status: result.status,
          latency_ms: result.latencyMs,
          response_keys: result.responseKeys,
          error: result.error,
        },
      };

      const response = await fetch(`${supabaseUrl}/rest/v1/health_heartbeat`, {
        method: "POST",
        headers: {
          apikey: supabaseKey,
          Authorization: `Bearer ${supabaseKey}`,
          "Content-Type": "application/json",
          Prefer: "resolution=merge-duplicates",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        console.log("      | Result stored in Supabase health_heartbeat");
      } else {
        console.log(`      | Supabase write failed (${response.status}), falling back to local log`);
        writeLocalLog(result);
      }
    } catch {
      console.log("      | Supabase unreachable, falling back to local log");
      writeLocalLog(result);
    }
  } else {
    writeLocalLog(result);
  }
}

function writeLocalLog(result: RhHealthResult) {
  const logDir = resolve(rootDir, "logs");
  mkdirSync(logDir, { recursive: true });
  const logPath = resolve(logDir, "rh_crypto_health.log");
  const entry = JSON.stringify({
    ts: new Date().toISOString(),
    ...result,
  });
  appendFileSync(logPath, entry + "\n", "utf-8");
  console.log(`      | Result appended to ${logPath}`);
}

main().catch((err) => {
  console.error("FAIL  | Unexpected error:", err instanceof Error ? err.message : err);
  process.exit(1);
});
