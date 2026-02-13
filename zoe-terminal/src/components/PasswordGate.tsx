import { useState, useEffect, type FormEvent } from 'react';
import { useAuth } from '../lib/AuthContext';

const HASH_KEY = 'zoe_auth_hash';

/** SHA-256 hash a string (browser native). */
async function sha256(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const buf = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

// Pre-computed SHA-256 hashes so plaintext passwords never appear in the bundle.
const ADMIN_HASH = '08adc3ca68d3246a4be26da96b546de92701c2b03df03da1508cf748edeccc1c';
const GUEST_HASH = '7ecc15e1b4dc6d70f79b8bf5c72ffcfa844c415c414d81f9e6247491d94ec28e';

type Role = 'admin' | 'guest';

function resolveRole(hash: string): Role | null {
  if (hash === ADMIN_HASH) return 'admin';
  if (hash === GUEST_HASH) return 'guest';
  return null;
}

export default function PasswordGate({ children }: { children: React.ReactNode }) {
  const { login } = useAuth();
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [input, setInput] = useState('');
  const [error, setError] = useState(false);

  // Check localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(HASH_KEY);
    if (stored && resolveRole(stored)) {
      // Ensure AuthContext role matches what's stored
      const storedRole = resolveRole(stored);
      if (storedRole) login(storedRole);
      setAuthed(true);
    } else {
      setAuthed(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const inputHash = await sha256(input);
    const resolvedRole = resolveRole(inputHash);
    if (resolvedRole) {
      localStorage.setItem(HASH_KEY, inputHash);
      login(resolvedRole);
      setAuthed(true);
      setError(false);
    } else {
      setError(true);
      setInput('');
    }
  };

  const handleGuestAccess = () => {
    localStorage.setItem(HASH_KEY, GUEST_HASH);
    login('guest');
    setAuthed(true);
  };

  // Loading state while checking auth
  if (authed === null) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-text-muted text-sm animate-pulse">Loading...</div>
      </div>
    );
  }

  if (authed) return <>{children}</>;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="bg-surface border border-border rounded-[20px] p-8 shadow-soft">
          {/* Logo / Title */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-black tracking-tighter text-text-primary">
              ZOE<span className="text-profit">_</span>TERMINAL
            </h1>
            <p className="text-text-muted text-xs mt-2 tracking-wide uppercase">
              Restricted Access
            </p>
          </div>

          {/* Admin Login */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[10px] text-text-muted font-bold uppercase tracking-widest mb-2 pl-1">
                Admin Password
              </label>
              <input
                type="password"
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setError(false);
                }}
                placeholder="Enter admin password"
                autoFocus
                className="w-full bg-surface-base border border-border rounded-[14px] px-4 py-3 text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-profit/50 focus:ring-1 focus:ring-profit/30 transition-all"
              />
              {error && (
                <p className="text-loss text-xs mt-2 pl-1">
                  Incorrect password
                </p>
              )}
            </div>
            <button
              type="submit"
              className="w-full bg-profit/10 hover:bg-profit/20 text-profit border border-profit/20 rounded-[14px] py-3 text-sm font-bold tracking-wide uppercase transition-all hover:shadow-[0_0_20px_rgba(46,229,157,0.15)]"
            >
              Access Dashboard
            </button>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-border" />
            <span className="text-[10px] text-text-dim font-bold uppercase tracking-widest">or</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Guest Button */}
          <button
            onClick={handleGuestAccess}
            className="w-full bg-white/[0.03] hover:bg-white/[0.06] text-text-muted hover:text-text-secondary border border-border hover:border-border/80 rounded-[14px] py-3 text-sm font-bold tracking-wide uppercase transition-all"
          >
            Enter as Guest
          </button>
          <p className="text-text-dim text-[9px] text-center mt-2 tracking-wide">
            View-only access — no trading controls
          </p>
        </div>

        <div className="text-center mt-6 space-y-1">
          <p className="text-text-dim text-[10px] tracking-wider uppercase">
            Zoe Trading System v4
          </p>
          <p className="text-text-dim/60 text-[9px] tracking-wide">
            Planned &amp; Designed by Josh Andrewlavage | Tobie LLC
          </p>
        </div>
      </div>
    </div>
  );
}
