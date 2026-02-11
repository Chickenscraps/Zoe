/**
 * Tests for @zoe/research — connector behavior with no API keys
 */
import { describe, it, expect } from "vitest";
import {
  fetchGoogleTrends,
  fetchXPosts,
  fetchBloomberg,
} from "../../services/research/src/connectors.js";

describe("Research Connectors", () => {
  it("fetchGoogleTrends should return empty when no API key", async () => {
    const result = await fetchGoogleTrends(["SPY", "QQQ"], {});
    expect(result).toEqual([]);
  });

  it("fetchXPosts should return empty when no bearer token", async () => {
    const result = await fetchXPosts(["SPY"], {});
    expect(result).toEqual([]);
  });

  it("fetchBloomberg should return stubs when no API key", async () => {
    const result = await fetchBloomberg(["SPY", "QQQ"], {});
    expect(result.length).toBe(2);
    expect(result[0]!.source).toBe("bloomberg");
    expect(result[0]!.metadata?.stub).toBe(true);
    expect(result[0]!.content).toContain("licensed");
  });

  it("Bloomberg stubs should have correct symbols", async () => {
    const result = await fetchBloomberg(["AAPL", "TSLA"], {});
    expect(result[0]!.symbol).toBe("AAPL");
    expect(result[1]!.symbol).toBe("TSLA");
  });

  it("Bloomberg stubs should have unique IDs", async () => {
    const result = await fetchBloomberg(["SPY", "QQQ"], {});
    expect(result[0]!.id).not.toBe(result[1]!.id);
  });
});
