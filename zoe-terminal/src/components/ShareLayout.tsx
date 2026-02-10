import React from 'react';

interface ShareLayoutProps {
  children: React.ReactNode;
  title?: string;
}

export function ShareLayout({ children, title }: ShareLayoutProps) {
  return (
    <div className="w-[1280px] h-[720px] bg-background text-text-primary p-12 flex flex-col items-center justify-center relative overflow-hidden bg-gradient-to-br from-background to-surface-highlight/10">
      
      {/* Background Decor */}
      <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-brand/5 rounded-full blur-[120px] -mr-48 -mt-48" />
      <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-blue-500/5 rounded-full blur-[100px] -ml-24 -mb-24" />

      {/* Header Branding */}
      <div className="absolute top-8 left-12 right-12 flex justify-between items-center z-10">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-black italic tracking-tighter text-white">ZOE V4</h1>
          <div className="h-4 w-px bg-border" />
          <span className="text-sm font-mono text-text-secondary uppercase tracking-widest">{title || 'INTERNAL TICKET'}</span>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-text-muted uppercase tracking-wider font-bold">Instance ID</span>
            <span className="text-xs font-mono text-white">primary-v4-live</span>
          </div>
          <div className="bg-blue-500/20 border border-blue-500/30 text-blue-400 px-3 py-1 rounded-sm text-xs font-black tracking-widest">
            PAPER MODE
          </div>
        </div>
      </div>

      {/* Main Content (The Card) */}
      <div className="z-10 w-full flex justify-center items-center mt-8">
        {children}
      </div>

      {/* Footer / Timestamp */}
      <div className="absolute bottom-8 left-12 right-12 flex justify-between items-center text-[10px] text-text-muted font-mono uppercase tracking-widest">
        <span>AUTHENTICITY_VERIFIED_SHA256</span>
        <span>{new Date().toISOString()}</span>
      </div>
    </div>
  );
}
