import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency. Guards against NaN/Infinity — returns "$0.00" for bad values.
 */
export function formatCurrency(value: number, currency = 'USD'): string {
  if (!isFinite(value) || isNaN(value)) return '$0.00';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(value);
}

/**
 * Format a number as percentage. Guards against NaN/Infinity — returns "0.00%" for bad values.
 */
export function formatPercentage(value: number, decimals = 2): string {
  if (!isFinite(value) || isNaN(value)) return '0.00%';
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value / 100);
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/** Format a number as BTC with 8 decimal places (e.g., "0.00123456 BTC") */
export function formatBTC(value: number): string {
  if (!isFinite(value) || value === 0) return "0.00000000 BTC";
  return `${value.toFixed(8)} BTC`;
}

/** Format an ISO date string or Unix epoch as a human-readable age (e.g., "2h 15m", "3d") */
export function formatAge(isoStringOrEpoch: string | number): string {
  let ms: number;
  if (typeof isoStringOrEpoch === "number") {
    // Accept seconds (Kraken) or milliseconds
    const epoch = isoStringOrEpoch > 1e12 ? isoStringOrEpoch : isoStringOrEpoch * 1000;
    ms = Date.now() - epoch;
  } else {
    ms = Date.now() - new Date(isoStringOrEpoch).getTime();
  }
  if (!isFinite(ms) || ms < 0) return "\u2014";
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  const remMin = min % 60;
  if (hr < 24) return remMin > 0 ? `${hr}h ${remMin}m` : `${hr}h`;
  const days = Math.floor(hr / 24);
  return `${days}d`;
}

/**
 * Safe number display — returns a dash for NaN/undefined/null values.
 * Use as a fallback in any data display context.
 */
export function safeNumber(value: number | null | undefined): string {
  if (value == null || !isFinite(value) || isNaN(value)) return '\u2014';
  return String(value);
}
