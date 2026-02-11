/**
 * Pre-Open Briefing Generator
 * Generates 15/10/5 minute briefings before market open.
 * Summarizes the plan, watchlist, and proposed plays.
 */
import { createLogger } from "../../shared/src/logger.js";
import { minutesToMarketOpen, getCurrentSession } from "../../shared/src/market-session.js";
import type { DailyPlan, ProposedPlay } from "../../shared/src/types.js";

const log = createLogger("trader:briefing");

export type BriefingType = "15min" | "10min" | "5min" | "at_open";

export interface Briefing {
  type: BriefingType;
  timestamp: string;
  minutesToOpen: number;
  summary: string;
  watchlist: string[];
  proposedPlays: ProposedPlay[];
  marketContext: string;
}

/**
 * Determine which briefing to generate based on time to market open.
 */
export function getBriefingType(minutesLeft: number): BriefingType | null {
  if (minutesLeft <= 0) return "at_open";
  if (minutesLeft <= 5) return "5min";
  if (minutesLeft <= 10) return "10min";
  if (minutesLeft <= 15) return "15min";
  return null;
}

/**
 * Generate a pre-open briefing from the daily plan.
 */
export function generateBriefing(
  plan: DailyPlan | null,
  minutesLeft: number
): Briefing | null {
  const type = getBriefingType(minutesLeft);
  if (!type) return null;

  const watchlist = plan?.watchlist ?? [];
  const plays = plan?.proposed_plays ?? [];
  const context = plan?.market_context ?? "No market context available.";

  let summary: string;
  switch (type) {
    case "15min":
      summary = `15 minutes to open. Watching ${watchlist.length} symbols with ${plays.length} proposed plays.`;
      break;
    case "10min":
      summary = `10 minutes to open. Final checks on ${plays.length} plays. Key levels in focus.`;
      break;
    case "5min":
      summary = `5 minutes to open. Ready to execute. ${plays.length} plays queued.`;
      break;
    case "at_open":
      summary = `Market is open. Executing scan → shortlist → decision loop.`;
      break;
  }

  const briefing: Briefing = {
    type,
    timestamp: new Date().toISOString(),
    minutesToOpen: minutesLeft,
    summary,
    watchlist,
    proposedPlays: plays,
    marketContext: context,
  };

  log.info("Briefing generated", { type, minutesToOpen: minutesLeft, plays: plays.length });
  return briefing;
}

/**
 * Check if a briefing should be sent now.
 * Returns the briefing type or null if no briefing is due.
 */
export function shouldSendBriefing(
  lastBriefingType: BriefingType | null,
  now: Date = new Date()
): BriefingType | null {
  const session = getCurrentSession(now);
  if (session !== "pre_market") return null;

  const minutes = minutesToMarketOpen(now);
  if (minutes === null) return null;

  const type = getBriefingType(minutes);
  if (!type) return null;

  // Don't repeat the same briefing type
  if (type === lastBriefingType) return null;

  return type;
}
