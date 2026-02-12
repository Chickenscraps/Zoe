import { useRef, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { initAuditMode } from './utils/ui_audit';
import { AppShell } from './components/AppShell';
import { TradeToastContainer, type ToastAPI } from './components/TradeToast';
import { useTradeNotifications } from './hooks/useTradeNotifications';
import { initAudio } from './lib/chime';
import Overview from './pages/Overview';
import Positions from './pages/Positions';
import Trades from './pages/Trades';
import TradeDetail from './pages/TradeDetail';
import Scanner from './pages/Scanner';
import Charts from './pages/Charts';
import Intelligence from './pages/Intelligence';
import Health from './pages/Health';
import Settings from './pages/Settings';

import ShareTrade from './pages/share/ShareTrade';
import SharePnL from './pages/share/SharePnL';
import SharePosition from './pages/share/SharePosition';
import SharePlan from './pages/share/SharePlan';

function AppWithNotifications() {
  const toastRef = useRef<ToastAPI | null>(null);

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

  // Subscribe to realtime trade events
  useTradeNotifications(toastRef);

  return (
    <>
      <AppShell>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/positions" element={<Positions />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/trades/:id" element={<TradeDetail />} />
          <Route path="/scanner" element={<Scanner />} />
          <Route path="/charts" element={<Charts />} />
          <Route path="/intelligence" element={<Intelligence />} />
          <Route path="/health" element={<Health />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </AppShell>
      <TradeToastContainer apiRef={toastRef} />
    </>
  );
}

function App() {
  useEffect(() => {
    const cleanup = initAuditMode();
    return () => { cleanup?.(); };
  }, []);

  return (
    <Router>
      <Routes>
        {/* Share Routes (No Shell, No Notifications) */}
        <Route path="/share/trade/:id" element={<ShareTrade />} />
        <Route path="/share/pnl" element={<SharePnL />} />
        <Route path="/share/position/:id" element={<SharePosition />} />
        <Route path="/share/plan" element={<SharePlan />} />

        {/* Main App with Notifications */}
        <Route path="*" element={<AppWithNotifications />} />
      </Routes>
    </Router>
  );
}

export default App;
