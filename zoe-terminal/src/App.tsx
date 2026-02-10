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

function App() {
  return (
    <Router>
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
    </Router>
  );
}

export default App;
