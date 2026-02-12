/**
 * @zoe/shared — Barrel exports
 */
export * from "./types.js";
export * from "./config.js";
export * from "./market-session.js";
export { Logger, createLogger, type LogLevel, type LogEntry } from "./logger.js";
export {
  getDb,
  createDb,
  resetDb,
  table,
  insertRow,
  updateRows,
  auditLog,
  type TableName,
} from "./db.js";
export {
  strategyConfigSchema,
  validateConfig,
  safeValidateConfig,
  configChecksum,
  configDiff,
  getConfigValue,
  setConfigValue,
  DIAL_BOUNDS,
  PRESET_PROFILES,
  HIGH_RISK_DIALS,
  type StrategyConfig,
  type DialBounds,
} from "./strategy-config.js";
export { ConfigLoader, type ConfigMetadata } from "./config-loader.js";
