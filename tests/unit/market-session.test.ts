/**
 * Tests for market session awareness
 */
import { describe, it, expect } from "vitest";
import {
  isTradingDay,
  isEarlyClose,
  getCurrentSession,
  minutesToMarketOpen,
} from "../../services/shared/src/market-session.js";

describe("market session", () => {
  it("should detect weekends as non-trading days", () => {
    // 2026-02-14 is a Saturday
    const saturday = new Date("2026-02-14T12:00:00-05:00");
    expect(isTradingDay(saturday)).toBe(false);
  });

  it("should detect weekdays as trading days", () => {
    // 2026-02-10 is a Tuesday (and not a holiday)
    const tuesday = new Date("2026-02-10T12:00:00-05:00");
    expect(isTradingDay(tuesday)).toBe(true);
  });

  it("should detect holidays", () => {
    // 2026-01-01 is New Year's Day
    const newYears = new Date("2026-01-01T12:00:00-05:00");
    expect(isTradingDay(newYears)).toBe(false);
  });

  it("should identify market_open session during trading hours", () => {
    // 2026-02-10 at 10:30 AM ET
    const midMorning = new Date("2026-02-10T10:30:00-05:00");
    expect(getCurrentSession(midMorning)).toBe("market_open");
  });

  it("should identify pre_market session", () => {
    // 2026-02-10 at 7:00 AM ET
    const preMarket = new Date("2026-02-10T07:00:00-05:00");
    expect(getCurrentSession(preMarket)).toBe("pre_market");
  });

  it("should identify after_hours session", () => {
    // 2026-02-10 at 5:00 PM ET
    const afterHours = new Date("2026-02-10T17:00:00-05:00");
    expect(getCurrentSession(afterHours)).toBe("after_hours");
  });

  it("should identify closed session on weekends", () => {
    const saturday = new Date("2026-02-14T12:00:00-05:00");
    expect(getCurrentSession(saturday)).toBe("closed");
  });

  it("should return minutes to market open before 9:30", () => {
    // 2026-02-10 at 8:30 AM ET = 60 min to open
    const earlyMorning = new Date("2026-02-10T08:30:00-05:00");
    expect(minutesToMarketOpen(earlyMorning)).toBe(60);
  });

  it("should return 0 minutes after market open", () => {
    const midDay = new Date("2026-02-10T12:00:00-05:00");
    expect(minutesToMarketOpen(midDay)).toBe(0);
  });

  it("should return null on non-trading days", () => {
    const saturday = new Date("2026-02-14T08:00:00-05:00");
    expect(minutesToMarketOpen(saturday)).toBeNull();
  });

  it("should detect early close days", () => {
    // 2026-12-24 is an early close day
    expect(isEarlyClose(new Date("2026-12-24T12:00:00-05:00"))).toBe(true);
    // Regular day
    expect(isEarlyClose(new Date("2026-02-10T12:00:00-05:00"))).toBe(false);
  });
});
