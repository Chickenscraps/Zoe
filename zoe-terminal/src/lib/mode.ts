/**
 * Mode types and context re-exports.
 *
 * Runtime mode is managed by ModeContext (React context + localStorage).
 * Use `useModeContext()` in components/hooks for reactive mode switching.
 *
 * Legacy: MODE/isPaper/isLive are kept as static defaults for non-React code
 * (e.g. module-level initialization). They reflect the initial mode only
 * and will NOT update when the user toggles mode at runtime.
 */

export type { TradingMode } from './ModeContext';
export { useModeContext, ModeProvider } from './ModeContext';

// Static fallback for non-React contexts (initial value only, does not update)
const raw = typeof localStorage !== 'undefined'
  ? localStorage.getItem('zoe_mode')
  : null;
const envMode = import.meta.env.VITE_MODE_LOCK;

export const MODE = (raw === 'live' || raw === 'paper')
  ? raw
  : (envMode === 'paper' ? 'paper' : 'live') as 'paper' | 'live';

export const isPaper = MODE === 'paper';
export const isLive = MODE === 'live';
