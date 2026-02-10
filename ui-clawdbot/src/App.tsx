
import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Settings, Activity, Send, Command, RefreshCw, Trash2, CheckCircle2, XCircle } from 'lucide-react';
import axios from 'axios';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const API_BASE = "http://localhost:8000";

interface LogEntry {
  timestamp: string;
  mode: string;
  event: string;
  content: string;
  metadata_obj?: any;
}

export default function App() {
  const [messages, setMessages] = useState<{ role: 'user' | 'agent', text: string, status?: string }[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState({ mode: 'normal', pending_action: null as any });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchStatus();
    fetchLogs();
    const interval = setInterval(() => {
      fetchStatus();
      fetchLogs();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, logs]);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/status`);
      setStatus(res.data);
    } catch (e) {
      console.error("Status fetch failed", e);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/logs/organize`);
      setLogs(res.data.logs);
    } catch (e) {
      console.error("Logs fetch failed", e);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const msg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: 'user', text: msg }]);
    setLoading(true);

    try {
      const res = await axios.post(`${API_BASE}/chat`, { message: msg });
      setMessages(prev => [...prev, { role: 'agent', text: res.data.response }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'agent', text: "Error connecting to backend.", status: 'error' }]);
    } finally {
      setLoading(false);
      fetchStatus();
    }
  };

  return (
    <div className="flex h-screen w-screen p-6 gap-6 max-h-screen overflow-hidden">
      {/* Sidebar - Proactive Nudges & Logs */}
      <motion.div 
        initial={{ x: -100, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        className="w-80 flex flex-col gap-6"
      >
        <div className="glass-card flex-1 flex flex-col p-4 overflow-hidden">
          <div className="flex items-center gap-2 mb-4 px-2">
            <Activity className="w-5 h-5 text-primary" />
            <h2 className="font-bold text-sm tracking-widest uppercase opacity-50">Proactive Feed</h2>
          </div>
          
          <div className="flex-1 overflow-y-auto space-y-3 pr-2" ref={scrollRef}>
            {logs.filter(l => l.event.includes('proactive') || l.event.includes('voice')).map((log, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="p-3 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors"
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="text-[10px] opacity-40">{new Date(log.timestamp).toLocaleTimeString()}</span>
                  <span className={cn(
                    "text-[8px] px-1.5 py-0.5 rounded-full uppercase font-bold",
                    log.event === 'proactive.nudge' ? "bg-primary/20 text-primary" : "bg-accent/20 text-accent"
                  )}>
                    {log.event.split('.')[1]}
                  </span>
                </div>
                <p className="text-xs leading-relaxed opacity-80">{log.content}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Status Card */}
        <div className="glass-card p-4 space-y-4">
          <div className="flex justify-between items-center px-2">
            <span className="text-[10px] opacity-40 uppercase tracking-widest font-bold">System Status</span>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[10px] text-green-500 font-bold uppercase">Online</span>
            </div>
          </div>
          <div className="flex items-center justify-between p-3 rounded-xl bg-white/5">
            <div className="flex items-center gap-3">
              <Command className="w-5 h-5 text-secondary" />
              <div>
                <p className="text-[10px] opacity-40 uppercase font-bold">Active Mode</p>
                <p className="text-sm font-bold capitalize">{status.mode}</p>
              </div>
            </div>
            <RefreshCw className="w-4 h-4 opacity-20 hover:opacity-100 transition-opacity cursor-pointer" onClick={fetchStatus} />
          </div>
        </div>
      </motion.div>

      {/* Main Content - Chat */}
      <motion.div 
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="flex-1 glass-card flex flex-col overflow-hidden"
      >
        {/* Chat Header */}
        <div className="p-6 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl overflow-hidden shadow-lg shadow-primary/20">
              <img src="/assets/mr-gagger-icon.png" alt="Mr Gagger" className="w-full h-full object-cover" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Mr Gagger Assistant</h1>
              <p className="text-xs opacity-50 flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-green-500" /> Always-on ops cofounder
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button 
              aria-label="Settings"
              className="p-3 rounded-xl hover:bg-white/5 transition-colors opacity-40 hover:opacity-100"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center space-y-4 opacity-20">
              <Command className="w-12 h-12" />
              <p className="text-sm font-medium">Listening for your command...</p>
            </div>
          )}
          
          <AnimatePresence>
            {messages.map((msg, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                className={cn(
                  "flex flex-col max-w-[80%]",
                  msg.role === 'user' ? "ml-auto items-end" : "items-start"
                )}
              >
                <div className={cn(
                  "p-4 rounded-2xl text-sm leading-relaxed shadow-sm",
                  msg.role === 'user' 
                    ? "bg-primary/20 border border-primary/20 text-white rounded-br-none" 
                    : "glass border-white/5 text-white/90 rounded-bl-none"
                )}>
                  {msg.text}
                </div>
                <span className="text-[10px] mt-1.5 opacity-30 font-medium">
                  {msg.role === 'user' ? 'You' : 'Mr Gagger'}
                </span>
              </motion.div>
            ))}
            
            {status.pending_action && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="p-6 rounded-2xl border border-secondary/30 bg-secondary/5 self-center w-[90%] flex flex-col items-center text-center space-y-4"
              >
                <div className="w-12 h-12 rounded-full bg-secondary/20 flex items-center justify-center">
                  <Command className="w-6 h-6 text-secondary" />
                </div>
                <div>
                  <h3 className="font-bold text-lg">Confirmation Required</h3>
                  <p className="text-sm opacity-60">I've prepared a draft for: <span className="font-bold text-white">{status.pending_action.content}</span></p>
                </div>
                <div className="flex gap-3">
                  <button 
                    onClick={() => { setInput("Confirm"); handleSend(); }}
                    className="flex items-center gap-2 px-6 py-2.5 bg-secondary text-white rounded-xl font-bold text-sm hover:brightness-110 transition-all shadow-lg shadow-secondary/20"
                  >
                    <CheckCircle2 className="w-4 h-4" /> Confirm
                  </button>
                  <button 
                    onClick={() => { setInput("Cancel"); handleSend(); }}
                    className="flex items-center gap-2 px-6 py-2.5 bg-white/5 hover:bg-white/10 text-white/60 rounded-xl font-bold text-sm transition-all"
                  >
                    <XCircle className="w-4 h-4" /> Cancel
                  </button>
                </div>
              </motion.div>
            )}

            {loading && (
              <motion.div 
                initial={{ opacity: 0 }} 
                animate={{ opacity: 1 }} 
                className="flex gap-1.5 px-4"
              >
                <div className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" />
                <div className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce [animation-delay:0.2s]" />
                <div className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce [animation-delay:0.4s]" />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Chat Input */}
        <div className="p-6 bg-white/[0.02] border-t border-white/10">
          <div className="relative flex items-center">
            <input 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Message Mr Gagger..."
              className="w-full bg-white/5 border border-white/5 focus:border-primary/50 focus:bg-white/10 transition-all rounded-2xl py-4 pl-6 pr-14 text-sm outline-none placeholder:opacity-20"
            />
            <button 
              onClick={handleSend}
              disabled={!input.trim() || loading}
              aria-label="Send message"
              className="absolute right-3 p-2 bg-gradient-to-br from-primary to-secondary rounded-xl disabled:opacity-20 disabled:grayscale transition-all hover:scale-105 active:scale-95 shadow-lg shadow-primary/20"
            >
              <Send className="w-5 h-5 text-white" />
            </button>
          </div>
          <div className="mt-4 flex items-center justify-between px-2">
            <div className="flex gap-4">
              <button 
                onClick={() => { setInput("Mode: Normal"); handleSend(); }}
                className="text-[10px] font-bold uppercase tracking-widest opacity-30 hover:opacity-100 transition-opacity"
              >
                Normal
              </button>
              <button 
                onClick={() => { setInput("Mode: Organize"); handleSend(); }}
                className="text-[10px] font-bold uppercase tracking-widest opacity-30 hover:opacity-100 transition-opacity"
              >
                Organize
              </button>
              <button 
                onClick={() => { setInput("Mode: Trade"); handleSend(); }}
                className="text-[10px] font-bold uppercase tracking-widest opacity-30 hover:opacity-100 transition-opacity"
              >
                Trade
              </button>
            </div>
            <p className="text-[10px] opacity-20 font-medium">Ctrl + Enter to send</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
