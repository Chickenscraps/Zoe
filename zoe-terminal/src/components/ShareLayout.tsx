import React from 'react';

interface ShareLayoutProps {
  children: React.ReactNode;
  title?: string;
}

export function ShareLayout({ children, title }: ShareLayoutProps) {
  return (
    <div className="screenshot-mode w-[1280px] h-[720px] bg-background text-text-primary p-16 flex flex-col items-center justify-center relative overflow-hidden font-sans">
      {/* Signature Background Pattern */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.03]">
        <div
          className="w-full h-full"
          style={{
            backgroundImage: 'linear-gradient(#452B27 1px, transparent 1px), linear-gradient(90deg, #452B27 1px, transparent 1px)',
            backgroundSize: '40px 40px'
          }}
        />
      </div>

      {/* Vignette Overlay */}
      <div className="absolute inset-0 pointer-events-none bg-gradient-radial from-transparent via-background/20 to-background opacity-80" />

      {/* Header Branding */}
      <div className="absolute top-12 left-16 right-16 flex justify-between items-end z-10">
        <div className="flex flex-col gap-1">
          <h1 className="font-pixel text-[0.65rem] uppercase tracking-[0.08em] text-gradient-accent">
            ZOE Terminal
          </h1>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-sakura-700 tracking-[0.2em] uppercase">{title || 'ANALYTICAL_TICKET'}</span>
            <div className="w-1 h-1 rounded-full bg-sakura-500" />
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-widest">v4.0.0-PRO</span>
          </div>
        </div>
        
        <div className="flex items-center gap-8">
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-text-muted uppercase tracking-[0.2em] font-semibold">Node Status</span>
            <span className="text-xs font-mono font-bold text-earth-700 uppercase group flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-sakura-500 animate-pulse" />
              INTEGRITY_VERIFIED
            </span>
          </div>
          <div className="bg-sakura-500/15 border-2 border-sakura-500/30 text-sakura-700 px-4 py-1.5 rounded-[4px] text-[10px] font-semibold tracking-[0.2em] uppercase">
            Analytics Mode
          </div>
        </div>
      </div>

      {/* Main Content (The Card) */}
      <div className="z-10 w-full flex justify-center items-center mt-12">
        {children}
      </div>

      {/* Footer / Timestamp */}
      <div className="absolute bottom-12 left-16 right-16 flex justify-between items-center text-[10px] text-text-muted font-semibold uppercase tracking-[0.3em]">
        <div className="flex items-center gap-4">
          <span>SECURED_BY_SUPABASE_SYSTEMS</span>
          <div className="w-4 h-px bg-earth-700/20" />
          <span>STATION_ID_ALPHA_PRIME</span>
        </div>
        <span>{new Date().toISOString()}</span>
      </div>
    </div>
  );
}
