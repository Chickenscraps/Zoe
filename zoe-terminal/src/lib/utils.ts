import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(value);
}

export function formatPercentage(value: number, decimals = 2): string {
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

export function formatBTC(value: number): string {
  if (!isFinite(value) || value === 0) return '0.00000000 BTC';
  return `${value.toFixed(8)} BTC`;
}

export function formatAge(isoStringOrEpoch: string | number): string {
  let ts: number;
  if (typeof isoStringOrEpoch === 'number') {
    // Kraken uses Unix epoch (seconds)
    ts = isoStringOrEpoch < 1e12 ? isoStringOrEpoch * 1000 : isoStringOrEpoch;
  } else {
    ts = new Date(isoStringOrEpoch).getTime();
  }
  if (isNaN(ts)) return '—';
  const seconds = Math.floor((Date.now() - ts) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainMin = minutes % 60;
  if (hours < 24) return remainMin > 0 ? `${hours}h ${remainMin}m` : `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}
