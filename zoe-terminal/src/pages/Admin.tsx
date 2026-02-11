import { useState, useEffect } from "react";
import { Shield, Lock, ExternalLink, CheckCircle, Eye, EyeOff } from "lucide-react";
import { StatusChip } from "../components/StatusChip";
import { useDashboardData } from "../hooks/useDashboardData";

export default function Admin() {
  const [pin, setPin] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [showSecrets, setShowSecrets] = useState(false);
  const [error, setError] = useState("");
  
  const { healthSummary } = useDashboardData();

  const CORRECT_PIN = "clawd"; // Simple client-side gate

  useEffect(() => {
    const saved = localStorage.getItem("zoe_admin_auth");
    if (saved === "true") setAuthenticated(true);
  }, []);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (pin === CORRECT_PIN) {
      setAuthenticated(true);
      localStorage.setItem("zoe_admin_auth", "true");
      setError("");
    } else {
      setError("Access Denied: Invalid PIN credential.");
      setPin("");
    }
  };

  const handleLogout = () => {
    setAuthenticated(false);
    localStorage.removeItem("zoe_admin_auth");
    setPin("");
  };

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 animate-in fade-in duration-700">
        <div className="p-4 rounded-full bg-brand-primary/10 border border-brand-primary/20">
          <Lock className="w-8 h-8 text-brand-primary" />
        </div>
        <h1 className="text-2xl font-black uppercase tracking-widest text-white">
          Restricted Area
        </h1>
        <p className="text-text-muted text-sm text-center max-w-md">
          This interface is protected. Authenticate to access system internals and sensitive configuration.
        </p>
        
        <form onSubmit={handleLogin} className="flex flex-col gap-4 w-full max-w-xs mt-4">
          <input
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="Enter Access PIN"
            className="bg-black/40 border border-border p-3 rounded text-center text-white tracking-[0.5em] focus:border-brand-primary focus:outline-none transition-colors"
            autoFocus
          />
          {error && <div className="text-loss text-xs text-center font-bold">{error}</div>}
          <button
            type="submit"
            className="bg-brand-primary text-black font-bold uppercase tracking-wider py-3 rounded hover:bg-brand-primary/90 transition-all active:scale-95"
          >
            Authenticate
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-risk-low/10 border border-risk-low/20">
            <Shield className="w-6 h-6 text-risk-low" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white uppercase tracking-wide">
              System Admin
            </h1>
            <p className="text-text-muted text-xs">
              Authenticated Session • {new Date().toLocaleTimeString()}
            </p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="text-xs text-text-muted hover:text-white uppercase font-bold tracking-wider hover:underline"
        >
          Logout
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* System Status Logic */}
        <div className="card-premium p-6">
          <h3 className="text-xs font-black uppercase tracking-[0.2em] text-text-muted mb-6 flex items-center gap-2">
             Configuration State
          </h3>
          <div className="space-y-4">
             <div className="flex items-center justify-between border-b border-border/40 pb-3">
                <span className="text-sm text-text-secondary">Trading Mode</span>
                <StatusChip 
                  status={healthSummary.status === "LIVE" ? "ok" : "warning"} 
                  label={healthSummary.status === "LIVE" ? "LIVE TRADING" : "PAPER (SIMULATION)"} 
                /> 
             </div>
             <div className="flex items-center justify-between border-b border-border/40 pb-3">
                <span className="text-sm text-text-secondary">Data Source</span>
                <div className="flex items-center gap-2 text-xs text-white">
                    <CheckCircle className="w-3 h-3 text-profit" /> Robinhood Crypto
                </div>
             </div>
             <div className="flex items-center justify-between border-b border-border/40 pb-3">
                <span className="text-sm text-text-secondary">Database Persistence</span>
                <div className="flex items-center gap-2 text-xs text-white">
                    <CheckCircle className="w-3 h-3 text-profit" /> Supabase
                </div>
             </div>
             <div className="flex items-center justify-between pt-1">
                <span className="text-sm text-text-secondary">Version</span>
                <span className="font-mono text-xs text-text-dim">v4.2.0-alpha</span>
             </div>
          </div>
        </div>

        {/* External Links */}
        <div className="card-premium p-6">
          <h3 className="text-xs font-black uppercase tracking-[0.2em] text-text-muted mb-6">
             Backend Portals
          </h3>
          <div className="flex flex-col gap-3">
            <a href="https://app.supabase.com" target="_blank" rel="noreferrer" className="flex items-center justify-between p-3 bg-background/50 border border-border rounded hover:border-brand-primary/50 transition-colors group">
               <span className="text-sm font-bold text-white group-hover:text-brand-primary transition-colors">Supabase Database</span>
               <ExternalLink className="w-4 h-4 text-text-muted" />
            </a>
            <a href="https://app.netlify.com" target="_blank" rel="noreferrer" className="flex items-center justify-between p-3 bg-background/50 border border-border rounded hover:border-brand-primary/50 transition-colors group">
               <span className="text-sm font-bold text-white group-hover:text-brand-primary transition-colors">Netlify Hosting</span>
               <ExternalLink className="w-4 h-4 text-text-muted" />
            </a>
            <a href="https://robinhood.com/crypto" target="_blank" rel="noreferrer" className="flex items-center justify-between p-3 bg-background/50 border border-border rounded hover:border-brand-primary/50 transition-colors group">
               <span className="text-sm font-bold text-white group-hover:text-brand-primary transition-colors">Robinhood Account</span>
               <ExternalLink className="w-4 h-4 text-text-muted" />
            </a>
          </div>
        </div>
      </div>

      {/* Sensitive Info Section */}
      <div className="card-premium p-6 border-risk-high/30">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xs font-black uppercase tracking-[0.2em] text-risk-high flex items-center gap-2">
            <Lock className="w-3 h-3" /> Sensitive Credentials
          </h3>
          <button
            onClick={() => setShowSecrets(!showSecrets)}
            className="text-xs flex items-center gap-2 text-text-muted hover:text-white"
          >
            {showSecrets ? <><EyeOff className="w-3 h-3" /> Hide</> : <><Eye className="w-3 h-3" /> Reveal (Unsafe)</>}
          </button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center border-b border-border/40 pb-4">
            <div className="text-sm font-bold text-text-secondary">Robinhood API Key</div>
            <div className="col-span-2 font-mono text-xs bg-black/40 p-2 rounded border border-border/50 text-text-dim break-all">
              {showSecrets ? (import.meta.env.VITE_RH_API_KEY_HINT || "Key not exposed to client bundle") : "••••••••-••••-••••-••••-••••••••••••"}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
            <div className="text-sm font-bold text-text-secondary">Supabase URL</div>
            <div className="col-span-2 font-mono text-xs bg-black/40 p-2 rounded border border-border/50 text-text-dim break-all">
              {showSecrets ? (import.meta.env.VITE_SUPABASE_URL || "Unknown") : "https://••••••••.supabase.co"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
