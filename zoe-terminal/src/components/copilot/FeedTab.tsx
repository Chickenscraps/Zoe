import { useRef, useEffect, useState } from 'react';
import { MessageSquare, Send, WifiOff, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useCopilotChat } from '../../hooks/useCopilotChat';
import { useCopilotFeed } from '../../hooks/useCopilotFeed';
import { SOURCE_CONFIG, getTradeChipColor } from '../../lib/copilotTypes';
import type { FeedItem, CopilotMessage } from '../../lib/copilotTypes';
export default function FeedTab() {
  const chat = useCopilotChat();
  const feed = useCopilotFeed();
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to top on new items (newest first)
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [chat.messages.length, feed.items.length]);

  const handleSend = () => {
    if (!input.trim()) return;
    chat.sendMessage(input);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full">

      {/* Feed + Chat messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {!chat.backendOnline && (
          <div className="flex items-center gap-2 px-3 py-2 bg-loss/10 border border-loss/20 rounded text-loss text-[11px] font-bold">
            <WifiOff className="w-3 h-3" /> Backend offline
          </div>
        )}

        {/* Interleave feed events and chat messages by timestamp */}
        {mergeTimeline(feed.items, chat.messages).map(entry => {
          if ('role' in entry) {
            return <ChatBubble key={entry.id} msg={entry} />;
          }
          return <FeedCard key={entry.id} item={entry} />;
        })}

        {feed.items.length === 0 && chat.messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-text-muted gap-3 py-12">
            <MessageSquare className="w-8 h-8 opacity-30" />
            <p className="text-xs font-medium">Ask Zoe anything about your trading data</p>
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="border-t border-border px-3 py-2">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="Message Zoe..."
            disabled={chat.isStreaming}
            className="flex-1 bg-surface-base border border-border px-3 py-2 text-xs text-text-primary placeholder:text-text-dim focus:outline-none focus:border-border-strong"
          />
          <button
            onClick={chat.isStreaming ? chat.stopStreaming : handleSend}
            disabled={!input.trim() && !chat.isStreaming}
            className={cn(
              "p-2 rounded transition-colors",
              chat.isStreaming
                ? "bg-loss/20 text-loss hover:bg-loss/30"
                : "bg-surface-highlight text-text-secondary hover:text-text-primary disabled:opacity-30"
            )}
          >
            {chat.isStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Merge feed items and chat messages into a single timeline, sorted newest-first. */
function mergeTimeline(feedItems: FeedItem[], chatMessages: CopilotMessage[]) {
  const all: Array<FeedItem | CopilotMessage> = [...feedItems, ...chatMessages];
  return all.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

function ChatBubble({ msg }: { msg: CopilotMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] px-3 py-2 text-xs leading-relaxed",
          isUser
            ? "bg-surface-highlight text-cream-100"
            : "bg-surface-base text-text-primary border border-border",
          msg.streaming && "opacity-80",
        )}
      >
        {msg.content || (msg.streaming ? <Loader2 className="w-3 h-3 animate-spin text-text-muted" /> : null)}
      </div>
    </div>
  );
}

/** Source-specific styling for visual differentiation */
const SOURCE_STYLES: Record<FeedItem['source'], { bg: string; border: string; badge: string }> = {
  trade:   { bg: 'bg-blue-500/5',   border: 'border-l-blue-400',   badge: 'bg-blue-500/15 text-blue-400' },
  thought: { bg: 'bg-purple-500/5', border: 'border-l-purple-400', badge: 'bg-purple-500/15 text-purple-400' },
  system:  { bg: 'bg-yellow-500/5', border: 'border-l-yellow-400', badge: 'bg-yellow-500/15 text-yellow-400' },
  config:  { bg: 'bg-slate-500/5',  border: 'border-l-slate-400',  badge: 'bg-slate-500/15 text-slate-400' },
  chat:    { bg: 'bg-emerald-500/5', border: 'border-l-emerald-400', badge: 'bg-emerald-500/15 text-emerald-400' },
};

function FeedCard({ item }: { item: FeedItem }) {
  const cfg = SOURCE_CONFIG[item.source];
  const style = SOURCE_STYLES[item.source];
  const isTrade = item.source === 'trade';
  const pnl = isTrade ? (item.metadata?.pnl as number | undefined) : undefined;
  const chipColor = isTrade ? getTradeChipColor(item.subtype, pnl) : cfg.color;

  // Severity overrides the source border color
  const borderColor =
    item.severity === 'critical' ? 'border-l-loss' :
    item.severity === 'warning' ? 'border-l-yellow-400' :
    item.severity === 'success' ? 'border-l-profit' :
    style.border;

  return (
    <div className={cn(
      "px-3 py-2 rounded border-l-2 text-[11px] transition-colors",
      style.bg,
      borderColor,
    )}>
      <div className="flex items-center gap-2 mb-0.5">
        {/* Source badge */}
        <span className={cn(
          "px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-widest",
          style.badge,
        )}>
          {cfg.label}
        </span>
        {/* Subtype */}
        <span className={cn("font-black uppercase tracking-widest text-[9px]", chipColor)}>
          {item.subtype.replace(/_/g, ' ')}
        </span>
        {item.symbol && (
          <span className="text-[9px] text-text-muted font-bold">{item.symbol}</span>
        )}
        <span className="ml-auto text-[9px] text-text-dim tabular-nums">
          {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
      <div className="text-text-secondary">{item.title}</div>
      {item.body && <div className="text-text-dim mt-0.5">{item.body}</div>}

      {/* Animated P&L chip */}
      {isTrade && pnl != null && (
        <span className={cn(
          "inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-black tabular-nums",
          pnl > 0 ? "bg-profit/10 text-profit pnl-pulse-green" : "bg-loss/10 text-loss pnl-pulse-red",
        )}>
          {pnl > 0 ? '+' : ''}{pnl.toFixed(2)}
        </span>
      )}
    </div>
  );
}
