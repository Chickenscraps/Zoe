import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import Overview from './pages/Overview';
import Positions from './pages/Positions';
import Trades from './pages/Trades';
import TradeDetail from './pages/TradeDetail';
import Scanner from './pages/Scanner';
import Plan from './pages/Plan';
import Thoughts from './pages/Thoughts';
import Health from './pages/Health';
import Settings from './pages/Settings';

import ShareTrade from './pages/share/ShareTrade';
import SharePnL from './pages/share/SharePnL';
import SharePosition from './pages/share/SharePosition';
import SharePlan from './pages/share/SharePlan';

function App() {
  return (
    <Router>
      <Routes>
        {/* Share Routes (No Shell) */}
        <Route path="/share/trade/:id" element={<ShareTrade />} />
        <Route path="/share/pnl" element={<SharePnL />} />
        <Route path="/share/position/:id" element={<SharePosition />} />
        <Route path="/share/plan" element={<SharePlan />} />

        {/* Protected App Shell */}
        <Route path="*" element={
          <AppShell>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/positions" element={<Positions />} />
              <Route path="/trades" element={<Trades />} />
              <Route path="/trades/:id" element={<TradeDetail />} />
              <Route path="/scanner" element={<Scanner />} />
              <Route path="/plan" element={<Plan />} />
              <Route path="/thoughts" element={<Thoughts />} />
              <Route path="/health" element={<Health />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </AppShell>
        } />
      </Routes>
    </Router>
  );
}

export default App;
