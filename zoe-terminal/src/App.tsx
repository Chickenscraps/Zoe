import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { initAuditMode } from './utils/ui_audit';
import { CopilotProvider } from './lib/CopilotContext';
import { AuthProvider } from './lib/AuthContext';
import PasswordGate from './components/PasswordGate';
import { AppShell } from './components/AppShell';
import { initAudio } from './lib/chime';
import Overview from './pages/Overview';
import Trades from './pages/Trades';
import TradeDetail from './pages/TradeDetail';
import Scanner from './pages/Scanner';
import Charts from './pages/Charts';
import Intelligence from './pages/Intelligence';
import Settings from './pages/Settings';

import ShareTrade from './pages/share/ShareTrade';
import SharePnL from './pages/share/SharePnL';
import SharePosition from './pages/share/SharePosition';
import SharePlan from './pages/share/SharePlan';

function AppContent() {
  // Initialize audio context on first user interaction
  useEffect(() => {
    const unlockAudio = () => {
      initAudio();
      document.removeEventListener('click', unlockAudio);
      document.removeEventListener('keydown', unlockAudio);
    };
    document.addEventListener('click', unlockAudio);
    document.addEventListener('keydown', unlockAudio);
    return () => {
      document.removeEventListener('click', unlockAudio);
      document.removeEventListener('keydown', unlockAudio);
    };
  }, []);

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/activity" element={<Trades />} />
        <Route path="/trades/:id" element={<TradeDetail />} />
        <Route path="/scanner" element={<Scanner />} />
        <Route path="/charts" element={<Charts />} />
        <Route path="/intelligence" element={<Intelligence />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </AppShell>
  );
}

function App() {
  useEffect(() => {
    const cleanup = initAuditMode();
    return () => { cleanup?.(); };
  }, []);

  return (
    <AuthProvider>
    <PasswordGate>
      <Router>
        <CopilotProvider>
          <Routes>
            {/* Share Routes (No Shell) */}
            <Route path="/share/trade/:id" element={<ShareTrade />} />
            <Route path="/share/pnl" element={<SharePnL />} />
            <Route path="/share/position/:id" element={<SharePosition />} />
            <Route path="/share/plan" element={<SharePlan />} />

            {/* Main App */}
            <Route path="*" element={<AppContent />} />
          </Routes>
        </CopilotProvider>
      </Router>
    </PasswordGate>
    </AuthProvider>
  );
}

export default App;
