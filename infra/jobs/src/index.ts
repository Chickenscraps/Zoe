/**
 * @zoe/jobs — Schedulers and cron for off-hours vs market hours
 * M9: Full implementation (self-heal, health checks, research triggers)
 */
import { createLogger, getCurrentSession, isTradingDay } from "@zoe/shared";

const log = createLogger("jobs");

export function describeSchedule(): void {
  const session = getCurrentSession();
  const tradingDay = isTradingDay();
  log.info("Schedule context", { session, tradingDay });
}
