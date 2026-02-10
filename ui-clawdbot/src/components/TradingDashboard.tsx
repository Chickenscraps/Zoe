import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, TrendingUp, DollarSign, Brain, Zap, Clock } from 'lucide-react';

interface Signal {
  id: string;
  topic: string;
  timestamp: string;
  summary: string;
}

interface Position {
  market_id: string;
  question: string;
  side: string;
  avg_price: number;
  shares: number;
  pnl: number;
}

interface Trade {
  side: string;
  market_question: string;
  timestamp: string;
}

interface Portfolio {
  total_equity: number;
  cash: number;
  pnl_24h: number;
  win_rate: number;
  positions: Position[];
}

interface DashboardData {
  status: string;
  last_updated: string;
  portfolio: Portfolio;
  signals: Signal[];
  recent_trades: Trade[];
}

const TradingDashboard = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const response = await fetch('/dashboard_data.json');
      const jsonData = await response.json();
      setData(jsonData);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="min-h-screen bg-black text-green-500 flex items-center justify-center font-mono">INITIALIZING SYSTEM...</div>;

  if (!data) return <div className="min-h-screen bg-black text-red-500 flex items-center justify-center font-mono">ERROR: NO DATA STREAM</div>;

  const { portfolio, signals, recent_trades } = data;

  return (
    <div className="min-h-screen bg-black text-gray-100 font-mono p-6">
      <header className="mb-8 border-b border-green-900 pb-4 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-green-500 flex items-center gap-2">
            <Brain className="w-8 h-8" />
            ZOE_TRADING_SYSTEM_V1
          </h1>
          <p className="text-xs text-gray-500 mt-1">STATUS: {data.status} | UPDATED: {new Date(data.last_updated).toLocaleTimeString()}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500">NET LIQUIDITY</p>
          <p className="text-2xl font-bold text-white">${portfolio.total_equity.toFixed(2)}</p>
        </div>
      </header>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left Col: Portfolio Stats */}
        <div className="md:col-span-1 space-y-6">
          <div className="bg-gray-900 border border-gray-800 p-4 rounded-lg">
            <h2 className="text-lg font-bold text-green-400 mb-4 flex items-center gap-2"><DollarSign className="w-4 h-4"/> Metrics</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-500">CASH</p>
                <p className="text-xl">${portfolio.cash.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">24H PNL</p>
                <p className={`text-xl ${portfolio.pnl_24h >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {portfolio.pnl_24h >= 0 ? '+' : ''}{portfolio.pnl_24h.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">WIN RATE</p>
                <p className="text-xl">{(portfolio.win_rate * 100).toFixed(0)}%</p>
              </div>
            </div>
          </div>

          <div className="bg-gray-900 border border-gray-800 p-4 rounded-lg">
            <h2 className="text-lg font-bold text-purple-400 mb-4 flex items-center gap-2"><Zap className="w-4 h-4"/> Active Signals</h2>
            <ul className="space-y-3">
              {signals.map((sig: Signal) => (
                <li key={sig.id} className="border-l-2 border-purple-500 pl-3 py-1">
                  <div className="flex justify-between items-start">
                    <span className="text-xs text-purple-300 font-bold">{sig.topic}</span>
                    <span className="text-[10px] text-gray-500">{new Date(sig.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-sm text-gray-300 mt-1">{sig.summary}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Right Col: Positions & Chart */}
        <div className="md:col-span-2 space-y-6">
          <div className="bg-gray-900 border border-gray-800 p-4 rounded-lg">
            <h2 className="text-lg font-bold text-blue-400 mb-4 flex items-center gap-2"><TrendingUp className="w-4 h-4"/> Active Positions</h2>
            {portfolio.positions.length === 0 ? (
              <p className="text-gray-500 text-sm italic">No active positions. Scanning markets...</p>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {portfolio.positions.map((pos: Position) => (
                    <div key={pos.market_id} className="bg-black border border-gray-700 p-3 rounded flex justify-between items-center">
                        <div>
                            <p className="font-bold text-sm text-white">{pos.question}</p>
                            <p className="text-xs text-gray-400">{pos.side} @ {pos.avg_price.toFixed(2)} ({pos.shares.toFixed(0)} shares)</p>
                        </div>
                        <div className="text-right">
                            <p className={`font-bold ${pos.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                {pos.pnl >= 0 ? '+' : ''}{pos.pnl.toFixed(2)}
                            </p>
                            <p className="text-xs text-gray-500">Unrealized PnL</p>
                        </div>
                    </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-gray-900 border border-gray-800 p-4 rounded-lg">
             <h2 className="text-lg font-bold text-yellow-400 mb-4 flex items-center gap-2"><Clock className="w-4 h-4"/> Recent Activity</h2>
             <div className="space-y-2">
                {recent_trades.length === 0 ? <p className="text-gray-500 text-sm">No recent trades.</p> : (
                    recent_trades.map((trade: Trade, i: number) => (
                        <div key={i} className="flex justify-between text-sm border-b border-gray-800 pb-1">
                            <span>{trade.side} {trade.market_question}</span>
                            <span className="text-gray-400">{new Date(trade.timestamp).toLocaleTimeString()}</span>
                        </div>
                    ))
                )}
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingDashboard;
