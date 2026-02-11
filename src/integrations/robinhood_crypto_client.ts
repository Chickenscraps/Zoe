/**
 * Robinhood Crypto Trading API Client
 *
 * READ-ONLY by default. POST/DELETE endpoints are gated behind RH_ALLOW_LIVE=true.
 * Uses Ed25519 signing per Robinhood's Crypto Trading API spec.
 *
 * Required env vars (store in .env.secrets):
 *   RH_CRYPTO_API_KEY          – API key from Robinhood developer portal
 *   RH_CRYPTO_PRIVATE_KEY_SEED – 32-byte Ed25519 seed, base64-encoded
 *   RH_CRYPTO_BASE_URL         – defaults to https://trading.robinhood.com
 *   RH_ALLOW_LIVE              – "true" to enable POST/DELETE; default "false"
 */

import { createPrivateKey, sign } from "node:crypto";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export interface RhCryptoConfig {
  apiKey: string;
  privateKeySeed: Buffer;
  baseUrl: string;
  allowLive: boolean;
}

export function loadRhCryptoConfig(): RhCryptoConfig {
  const apiKey = process.env.RH_CRYPTO_API_KEY ?? "";
  const seedRaw = process.env.RH_CRYPTO_PRIVATE_KEY_SEED ?? "";
  const baseUrl = (process.env.RH_CRYPTO_BASE_URL ?? "https://trading.robinhood.com").replace(
    /\/$/,
    "",
  );
  const allowLive = process.env.RH_ALLOW_LIVE === "true";

  if (!apiKey) {
    throw new Error("RH_CRYPTO_API_KEY is not set");
  }
  if (!seedRaw) {
    throw new Error("RH_CRYPTO_PRIVATE_KEY_SEED is not set");
  }

  const privateKeySeed = Buffer.from(seedRaw, "base64");
  if (privateKeySeed.length !== 32) {
    throw new Error(
      `RH_CRYPTO_PRIVATE_KEY_SEED must decode to exactly 32 bytes (got ${privateKeySeed.length}). Provide the raw Ed25519 seed as base64.`,
    );
  }

  return { apiKey, privateKeySeed, baseUrl, allowLive };
}

// ---------------------------------------------------------------------------
// Canonical JSON serializer (deterministic, no whitespace)
// ---------------------------------------------------------------------------

export function canonicalJsonStringify(obj: unknown): string {
  return JSON.stringify(obj, Object.keys(obj as object).sort(), 0)
    ?.replace(/\n/g, "")
    ?.replace(/ /g, "") ?? stableStringify(obj);
}

/**
 * Stable stringify: deterministic key ordering, compact (no whitespace).
 * Handles nested objects/arrays correctly.
 */
export function stableStringify(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "boolean" || typeof value === "number") return JSON.stringify(value);
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return "[" + value.map((item) => stableStringify(item)).join(",") + "]";
  }
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>).sort();
    const pairs = keys.map(
      (key) => JSON.stringify(key) + ":" + stableStringify((value as Record<string, unknown>)[key]),
    );
    return "{" + pairs.join(",") + "}";
  }
  return String(value);
}

// ---------------------------------------------------------------------------
// Ed25519 Signing
// ---------------------------------------------------------------------------

/**
 * Build the message_to_sign per Robinhood spec:
 *   api_key + timestamp + api_path + http_method + request_body
 */
export function buildMessageToSign(
  apiKey: string,
  timestamp: string,
  path: string,
  method: string,
  body: string,
): string {
  return apiKey + timestamp + path + method.toUpperCase() + body;
}

/**
 * Sign a message with Ed25519 using the 32-byte seed.
 * Returns the base64-encoded signature.
 */
export function signMessage(message: string, seed: Buffer): string {
  // Node 22+ supports Ed25519 natively via createPrivateKey with JWK or raw DER.
  // We wrap the 32-byte seed in PKCS#8 DER for Ed25519.
  const pkcs8Prefix = Buffer.from(
    "302e020100300506032b657004220420",
    "hex",
  ); // PKCS#8 prefix for Ed25519 (48 bytes total)
  const pkcs8Der = Buffer.concat([pkcs8Prefix, seed]);

  const privateKey = createPrivateKey({
    key: pkcs8Der,
    format: "der",
    type: "pkcs8",
  });

  const signature = sign(null, Buffer.from(message, "utf-8"), privateKey);
  return signature.toString("base64");
}

/**
 * Build the three auth headers for a Robinhood Crypto API request.
 */
export function buildAuthHeaders(
  config: RhCryptoConfig,
  method: string,
  path: string,
  body: string,
  timestamp?: string,
): Record<string, string> {
  const ts = timestamp ?? Math.floor(Date.now() / 1000).toString();
  const message = buildMessageToSign(config.apiKey, ts, path, method, body);
  const sig = signMessage(message, config.privateKeySeed);

  return {
    "x-api-key": config.apiKey,
    "x-timestamp": ts,
    "x-signature": sig,
  };
}

// ---------------------------------------------------------------------------
// Structured error
// ---------------------------------------------------------------------------

export class RhCryptoError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly responseBody?: unknown,
  ) {
    super(message);
    this.name = "RhCryptoError";
  }
}

// ---------------------------------------------------------------------------
// Request helper with retry
// ---------------------------------------------------------------------------

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 500;

/**
 * Core request helper for Robinhood Crypto Trading API.
 *
 * - Produces signed headers automatically.
 * - Retries with exponential backoff on 429 / 5xx (max 3 attempts).
 * - POST/DELETE hard-fail unless RH_ALLOW_LIVE=true.
 * - Never leaks secrets in errors.
 */
export async function rhRequest(
  method: string,
  path: string,
  options?: {
    body?: Record<string, unknown>;
    query?: Record<string, string>;
    config?: RhCryptoConfig;
  },
): Promise<{ status: number; data: unknown }> {
  const config = options?.config ?? loadRhCryptoConfig();
  const upperMethod = method.toUpperCase();

  // Safety gate: block mutating calls unless live trading is explicitly allowed
  if (!SAFE_METHODS.has(upperMethod) && !config.allowLive) {
    throw new RhCryptoError(
      `Live trading is disabled (RH_ALLOW_LIVE=false). Cannot execute ${upperMethod} ${path}`,
      0,
      "LIVE_DISABLED",
    );
  }

  // Build canonical body string
  const bodyString =
    options?.body && (upperMethod === "POST" || upperMethod === "PUT")
      ? stableStringify(options.body)
      : "";

  // Build full URL with query params
  let url = config.baseUrl + path;
  if (options?.query) {
    const params = new URLSearchParams(options.query);
    url += "?" + params.toString();
  }

  let lastError: Error | undefined;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      const delay = INITIAL_BACKOFF_MS * 2 ** (attempt - 1);
      await sleep(delay);
    }

    // Timestamp MUST be generated per attempt (Robinhood rejects stale timestamps)
    const authHeaders = buildAuthHeaders(config, upperMethod, path, bodyString);

    const headers: Record<string, string> = {
      ...authHeaders,
      "Content-Type": "application/json",
    };

    try {
      const response = await fetch(url, {
        method: upperMethod,
        headers,
        body: bodyString || undefined,
      });

      if (response.ok) {
        const contentType = response.headers.get("content-type") ?? "";
        const data = contentType.includes("application/json")
          ? await response.json()
          : await response.text();
        return { status: response.status, data };
      }

      // Retry on 429 or 5xx
      if (response.status === 429 || response.status >= 500) {
        lastError = new RhCryptoError(
          `HTTP ${response.status} from ${upperMethod} ${path}`,
          response.status,
          "RETRYABLE",
        );
        continue;
      }

      // Non-retryable client error
      let errorBody: unknown;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text().catch(() => null);
      }
      throw new RhCryptoError(
        `HTTP ${response.status} from ${upperMethod} ${path}`,
        response.status,
        "CLIENT_ERROR",
        errorBody,
      );
    } catch (err) {
      if (err instanceof RhCryptoError) throw err;
      // Network-level errors are retryable
      lastError = err instanceof Error ? err : new Error(String(err));
    }
  }

  throw new RhCryptoError(
    `Failed after ${MAX_RETRIES} attempts: ${lastError?.message ?? "unknown"}`,
    0,
    "EXHAUSTED_RETRIES",
  );
}

// ---------------------------------------------------------------------------
// Convenience methods for common endpoints
// ---------------------------------------------------------------------------

/** GET /api/v1/crypto/trading/accounts/ */
export async function getAccount(config?: RhCryptoConfig) {
  return rhRequest("GET", "/api/v1/crypto/trading/accounts/", { config });
}

/** GET /api/v1/crypto/trading/holdings/ */
export async function getHoldings(config?: RhCryptoConfig) {
  return rhRequest("GET", "/api/v1/crypto/trading/holdings/", { config });
}

/** GET /api/v1/crypto/trading/orders/ */
export async function getOrders(config?: RhCryptoConfig) {
  return rhRequest("GET", "/api/v1/crypto/trading/orders/", { config });
}

/** GET /api/v1/crypto/trading/trading_pairs/ */
export async function getTradingPairs(config?: RhCryptoConfig) {
  return rhRequest("GET", "/api/v1/crypto/trading/trading_pairs/", { config });
}

/** GET /api/v1/crypto/trading/best_bid_ask/ with ?symbol=... */
export async function getBestBidAsk(symbol: string, config?: RhCryptoConfig) {
  return rhRequest("GET", "/api/v1/crypto/trading/best_bid_ask/", {
    query: { symbol },
    config,
  });
}

/** GET /api/v1/crypto/trading/estimated_price/ with ?symbol=...&side=...&quantity=... */
export async function getEstimatedPrice(
  params: { symbol: string; side: "bid" | "ask" | "both"; quantity: string },
  config?: RhCryptoConfig,
) {
  return rhRequest("GET", "/api/v1/crypto/trading/estimated_price/", {
    query: { symbol: params.symbol, side: params.side, quantity: params.quantity },
    config,
  });
}

// ---------------------------------------------------------------------------
// Health probe (used by Zoe's /health system)
// ---------------------------------------------------------------------------

export interface RhHealthResult {
  ok: boolean;
  status: number;
  latencyMs: number;
  responseKeys?: string[];
  error?: string;
}

/**
 * Non-blocking health probe. Calls a safe GET endpoint and returns a summary
 * without leaking PII.
 */
export async function probeHealth(config?: RhCryptoConfig): Promise<RhHealthResult> {
  const start = Date.now();
  try {
    const cfg = config ?? loadRhCryptoConfig();
    const result = await rhRequest("GET", "/api/v1/crypto/trading/accounts/", { config: cfg });
    const latencyMs = Date.now() - start;
    const keys =
      result.data && typeof result.data === "object"
        ? Object.keys(result.data as object)
        : undefined;
    return { ok: true, status: result.status, latencyMs, responseKeys: keys };
  } catch (err) {
    const latencyMs = Date.now() - start;
    const status = err instanceof RhCryptoError ? err.status : 0;
    const message = err instanceof Error ? err.message : "unknown error";
    return { ok: false, status, latencyMs, error: message };
  }
}

/**
 * Returns true if the minimum required env vars are present (does not validate them).
 */
export function isConfigured(): boolean {
  return Boolean(process.env.RH_CRYPTO_API_KEY && process.env.RH_CRYPTO_PRIVATE_KEY_SEED);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
