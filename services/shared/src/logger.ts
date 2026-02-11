/**
 * Zoe V4 — Structured Logger
 * Lightweight wrapper that produces JSON-structured logs for observability.
 * All decisions and trade actions must be reproducible from logs.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  service: string;
  message: string;
  data?: Record<string, unknown>;
}

export class Logger {
  private service: string;
  private minLevel: LogLevel;

  constructor(service: string, minLevel?: LogLevel) {
    this.service = service;
    this.minLevel = minLevel ?? (process.env["LOG_LEVEL"] as LogLevel) ?? "info";
  }

  private shouldLog(level: LogLevel): boolean {
    return LEVEL_ORDER[level] >= LEVEL_ORDER[this.minLevel];
  }

  private emit(level: LogLevel, message: string, data?: Record<string, unknown>): void {
    if (!this.shouldLog(level)) return;

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      service: this.service,
      message,
      ...(data && { data }),
    };

    const line = JSON.stringify(entry);

    switch (level) {
      case "error":
        console.error(line);
        break;
      case "warn":
        console.warn(line);
        break;
      default:
        console.log(line);
    }
  }

  debug(message: string, data?: Record<string, unknown>): void {
    this.emit("debug", message, data);
  }

  info(message: string, data?: Record<string, unknown>): void {
    this.emit("info", message, data);
  }

  warn(message: string, data?: Record<string, unknown>): void {
    this.emit("warn", message, data);
  }

  error(message: string, data?: Record<string, unknown>): void {
    this.emit("error", message, data);
  }

  /** Log a trade decision with full context for reproducibility */
  tradeDecision(action: string, data: Record<string, unknown>): void {
    this.emit("info", `TRADE_DECISION: ${action}`, {
      ...data,
      _decision: true,
      _reproducible: true,
    });
  }

  child(subService: string): Logger {
    return new Logger(`${this.service}:${subService}`, this.minLevel);
  }
}

export function createLogger(service: string): Logger {
  return new Logger(service);
}
