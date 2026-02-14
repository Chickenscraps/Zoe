import { useState, useEffect, type FormEvent } from 'react';
import { useAuth } from '../lib/AuthContext';
import SnesWindow from './snes/SnesWindow';
import SnesButton from './snes/SnesButton';
import ParallaxBackground from './snes/ParallaxBackground';

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
        <div className="font-pixel text-[0.5rem] text-text-muted animate-pulse uppercase tracking-widest">Loading...</div>
      </div>
    );
  }

  if (authed) return <>{children}</>;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative">
      <ParallaxBackground />
      <div className="w-full max-w-sm relative z-10">
        <SnesWindow variant="focused" title="System Login">
          {/* Logo / Title */}
          <div className="text-center mb-6">
            <h1 className="font-pixel text-sm uppercase tracking-[0.08em] text-gradient-accent">
              ZOE Terminal
            </h1>
            <p className="text-text-muted text-xs mt-2 tracking-wide uppercase">
              Restricted Access
            </p>
          </div>

          {/* Admin Login */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block font-pixel text-[0.4rem] text-text-muted uppercase tracking-[0.1em] mb-2 pl-1">
                Password
              </label>
              <input
                type="password"
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setError(false);
                }}
                placeholder="Enter password"
                autoFocus
                className="w-full bg-cream-100 border-2 border-earth-700/15 px-4 py-3 text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-sakura-500 focus:ring-1 focus:ring-sakura-500/30 transition-all"
              />
              {error && (
                <p className="text-loss text-xs mt-2 pl-1 font-pixel text-[0.4rem]">
                  Incorrect password
                </p>
              )}
            </div>
            <SnesButton type="submit" className="w-full">
              Access Dashboard
            </SnesButton>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-earth-700/10" />
            <span className="font-pixel text-[0.35rem] text-text-dim uppercase tracking-widest">or</span>
            <div className="flex-1 h-px bg-earth-700/10" />
          </div>

          {/* Guest Button */}
          <SnesButton
            variant="secondary"
            onClick={handleGuestAccess}
            className="w-full"
          >
            Enter as Guest
          </SnesButton>
          <p className="text-text-dim text-[9px] text-center mt-2 tracking-wide">
            View-only access
          </p>
        </SnesWindow>

        <div className="text-center mt-6 space-y-1">
          <p className="font-pixel text-[0.35rem] text-text-dim tracking-wider uppercase">
            ZOE Market Intelligence v4
          </p>
          <p className="text-text-dim/60 text-[9px] tracking-wide">
            Planned &amp; Designed by Josh Andrewlavage | Tobie LLC
          </p>
        </div>
      </div>
    </div>
  );
}
