/**
 * Zoe V4 — Market Session Awareness
 * Determines current market state based on US equity calendar.
 * All times are Eastern Time (America/New_York).
 */
import type { MarketSession, MarketCalendarDay } from "./types.js";

// US market holidays (2025-2026). Add more as needed.
const MARKET_HOLIDAYS: Set<string> = new Set([
  // 2025
  "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
  "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01",
  "2025-11-27", "2025-12-25",
  // 2026
  "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
  "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
  "2026-11-26", "2026-12-25",
]);

// Early close days (1:00 PM ET close instead of 4:00 PM)
const EARLY_CLOSE_DAYS: Set<string> = new Set([
  "2025-07-03", "2025-11-28", "2025-12-24",
  "2026-07-02", "2026-11-27", "2026-12-24",
]);

function toET(date: Date): Date {
  // Convert to Eastern Time string, then parse
  const etStr = date.toLocaleString("en-US", { timeZone: "America/New_York" });
  return new Date(etStr);
}

function dateToKey(date: Date): string {
  const et = toET(date);
  const y = et.getFullYear();
  const m = String(et.getMonth() + 1).padStart(2, "0");
  const d = String(et.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function isTradingDay(date: Date = new Date()): boolean {
  const et = toET(date);
  const dayOfWeek = et.getDay();
  // Weekend
  if (dayOfWeek === 0 || dayOfWeek === 6) return false;
  // Holiday
  if (MARKET_HOLIDAYS.has(dateToKey(date))) return false;
  return true;
}

export function isEarlyClose(date: Date = new Date()): boolean {
  return EARLY_CLOSE_DAYS.has(dateToKey(date));
}

export function getCurrentSession(date: Date = new Date()): MarketSession {
  if (!isTradingDay(date)) return "closed";

  const et = toET(date);
  const hours = et.getHours();
  const minutes = et.getMinutes();
  const timeMinutes = hours * 60 + minutes;

  const preMarketOpen = 4 * 60;        // 4:00 AM
  const marketOpen = 9 * 60 + 30;      // 9:30 AM
  const marketClose = isEarlyClose(date) ? 13 * 60 : 16 * 60; // 1:00 PM or 4:00 PM
  const afterHoursClose = 20 * 60;     // 8:00 PM

  if (timeMinutes >= preMarketOpen && timeMinutes < marketOpen) return "pre_market";
  if (timeMinutes >= marketOpen && timeMinutes < marketClose) return "market_open";
  if (timeMinutes >= marketClose && timeMinutes < afterHoursClose) return "after_hours";
  return "closed";
}

export function getMarketCalendarDay(date: Date = new Date()): MarketCalendarDay {
  const dateKey = dateToKey(date);
  const trading = isTradingDay(date);
  const early = isEarlyClose(date);

  return {
    date: dateKey,
    is_trading_day: trading,
    market_open: trading ? `${dateKey}T09:30:00-05:00` : null,
    market_close: trading
      ? early
        ? `${dateKey}T13:00:00-05:00`
        : `${dateKey}T16:00:00-05:00`
      : null,
    early_close: early,
    session: getCurrentSession(date),
  };
}

/**
 * Minutes until market open from the given time.
 * Returns 0 if market is already open. Returns null if not a trading day.
 */
export function minutesToMarketOpen(date: Date = new Date()): number | null {
  if (!isTradingDay(date)) return null;
  const et = toET(date);
  const timeMinutes = et.getHours() * 60 + et.getMinutes();
  const marketOpen = 9 * 60 + 30;
  if (timeMinutes >= marketOpen) return 0;
  return marketOpen - timeMinutes;
}
