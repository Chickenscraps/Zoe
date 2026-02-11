import { describe, it, expect } from "vitest";
import {
  buildMessageToSign,
  signMessage,
  buildAuthHeaders,
  stableStringify,
  type RhCryptoConfig,
} from "./robinhood_crypto_client.js";

// ---------------------------------------------------------------------------
// Fixed test vectors
// ---------------------------------------------------------------------------

// Deterministic 32-byte Ed25519 seed (NOT a real secret — test only)
const TEST_SEED = Buffer.from(
  "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
  "base64",
);

const TEST_API_KEY = "test-api-key-12345";
const TEST_TIMESTAMP = "1700000000";
const TEST_PATH = "/api/v1/crypto/trading/orders/";

const TEST_CONFIG: RhCryptoConfig = {
  apiKey: TEST_API_KEY,
  privateKeySeed: TEST_SEED,
  baseUrl: "https://trading.robinhood.com",
  allowLive: false,
};

// ---------------------------------------------------------------------------
// stableStringify
// ---------------------------------------------------------------------------

describe("stableStringify", () => {
  it("produces deterministic key ordering", () => {
    const obj = { z: 1, a: 2, m: 3 };
    expect(stableStringify(obj)).toBe('{"a":2,"m":3,"z":1}');
  });

  it("produces compact output with no whitespace", () => {
    const obj = { hello: "world", num: 42 };
    const result = stableStringify(obj);
    expect(result).not.toContain(" ");
    expect(result).not.toContain("\n");
  });

  it("handles nested objects deterministically", () => {
    const obj = { b: { d: 1, c: 2 }, a: 3 };
    expect(stableStringify(obj)).toBe('{"a":3,"b":{"c":2,"d":1}}');
  });

  it("handles arrays", () => {
    const obj = { items: [3, 1, 2] };
    expect(stableStringify(obj)).toBe('{"items":[3,1,2]}');
  });

  it("handles null and booleans", () => {
    const obj = { flag: true, nothing: null, off: false };
    expect(stableStringify(obj)).toBe('{"flag":true,"nothing":null,"off":false}');
  });

  it("handles strings with special chars", () => {
    const obj = { msg: 'hello "world"' };
    expect(stableStringify(obj)).toBe('{"msg":"hello \\"world\\""}');
  });

  it("is idempotent", () => {
    const obj = { z: 1, a: { c: 3, b: 2 } };
    expect(stableStringify(obj)).toBe(stableStringify(obj));
  });
});

// ---------------------------------------------------------------------------
// buildMessageToSign
// ---------------------------------------------------------------------------

describe("buildMessageToSign", () => {
  it("concatenates fields in the correct order", () => {
    const msg = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "GET", "");
    expect(msg).toBe(
      "test-api-key-123451700000000/api/v1/crypto/trading/orders/GET",
    );
  });

  it("includes body for POST", () => {
    const body = '{"symbol":"BTC-USD","quantity":"0.001"}';
    const msg = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "POST", body);
    expect(msg).toBe(
      `test-api-key-123451700000000/api/v1/crypto/trading/orders/POST${body}`,
    );
  });

  it("uppercases method", () => {
    const msg = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "get", "");
    expect(msg).toContain("GET");
    expect(msg).not.toContain("get");
  });
});

// ---------------------------------------------------------------------------
// signMessage — deterministic signature for fixed seed + message
// ---------------------------------------------------------------------------

describe("signMessage", () => {
  it("produces a base64-encoded signature", () => {
    const message = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "GET", "");
    const sig = signMessage(message, TEST_SEED);

    // Valid base64 string
    expect(sig).toMatch(/^[A-Za-z0-9+/]+=*$/);
    // Ed25519 signature is 64 bytes → 88 base64 chars
    expect(Buffer.from(sig, "base64")).toHaveLength(64);
  });

  it("is deterministic (same input → same signature)", () => {
    const message = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "GET", "");
    const sig1 = signMessage(message, TEST_SEED);
    const sig2 = signMessage(message, TEST_SEED);
    expect(sig1).toBe(sig2);
  });

  it("changes when the message changes", () => {
    const msg1 = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "GET", "");
    const msg2 = buildMessageToSign(TEST_API_KEY, "1700000001", TEST_PATH, "GET", "");
    const sig1 = signMessage(msg1, TEST_SEED);
    const sig2 = signMessage(msg2, TEST_SEED);
    expect(sig1).not.toBe(sig2);
  });

  it("changes when the body changes for POST", () => {
    const body1 = stableStringify({ symbol: "BTC-USD", quantity: "0.001" });
    const body2 = stableStringify({ symbol: "ETH-USD", quantity: "0.01" });
    const msg1 = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "POST", body1);
    const msg2 = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "POST", body2);
    const sig1 = signMessage(msg1, TEST_SEED);
    const sig2 = signMessage(msg2, TEST_SEED);
    expect(sig1).not.toBe(sig2);
  });
});

// ---------------------------------------------------------------------------
// buildAuthHeaders
// ---------------------------------------------------------------------------

describe("buildAuthHeaders", () => {
  it("returns required x-api-key, x-timestamp, x-signature", () => {
    const headers = buildAuthHeaders(TEST_CONFIG, "GET", TEST_PATH, "", TEST_TIMESTAMP);
    expect(headers).toHaveProperty("x-api-key", TEST_API_KEY);
    expect(headers).toHaveProperty("x-timestamp", TEST_TIMESTAMP);
    expect(headers).toHaveProperty("x-signature");
    expect(headers["x-signature"]).toMatch(/^[A-Za-z0-9+/]+=*$/);
  });

  it("produces consistent headers for same inputs", () => {
    const h1 = buildAuthHeaders(TEST_CONFIG, "GET", TEST_PATH, "", TEST_TIMESTAMP);
    const h2 = buildAuthHeaders(TEST_CONFIG, "GET", TEST_PATH, "", TEST_TIMESTAMP);
    expect(h1).toEqual(h2);
  });

  it("uses body in signature for POST", () => {
    const body = stableStringify({ symbol: "BTC-USD" });
    const getHeaders = buildAuthHeaders(TEST_CONFIG, "GET", TEST_PATH, "", TEST_TIMESTAMP);
    const postHeaders = buildAuthHeaders(TEST_CONFIG, "POST", TEST_PATH, body, TEST_TIMESTAMP);
    // Same api key and timestamp, but different signature
    expect(getHeaders["x-api-key"]).toBe(postHeaders["x-api-key"]);
    expect(getHeaders["x-timestamp"]).toBe(postHeaders["x-timestamp"]);
    expect(getHeaders["x-signature"]).not.toBe(postHeaders["x-signature"]);
  });
});

// ---------------------------------------------------------------------------
// Snapshot: full round-trip determinism
// ---------------------------------------------------------------------------

describe("full signing round-trip", () => {
  it("matches a known snapshot for GET request", () => {
    const message = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "GET", "");
    const sig = signMessage(message, TEST_SEED);
    // Record the signature as a snapshot to detect regressions
    expect(sig).toMatchSnapshot();
  });

  it("matches a known snapshot for POST request", () => {
    const body = stableStringify({ quantity: "0.001", side: "buy", symbol: "BTC-USD", type: "market" });
    const message = buildMessageToSign(TEST_API_KEY, TEST_TIMESTAMP, TEST_PATH, "POST", body);
    const sig = signMessage(message, TEST_SEED);
    expect(sig).toMatchSnapshot();
  });
});
