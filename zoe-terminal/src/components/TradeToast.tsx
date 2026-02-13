/**
 * TradeToast — slide-in notification for buy/sell events.
 *
 * Renders a stack of toasts in the bottom-right corner.
 * Each toast auto-dismisses after a configurable duration.
 * Matches the Zoe Terminal design system (dark glass, profit/loss colors).
 */

import { useEffect, useState, useCallback, useRef } from "react";
import { ArrowUpRight, ArrowDownRight, Bell, X } from "lucide-react";
import { cn, formatCurrency } from "../lib/utils";

export type ToastType = "buy" | "sell" | "alert" | "error";

export interface TradeToastData {
  id: string;
  type: ToastType;
  symbol: string;
  message: string;
  amount?: number;
  timestamp: Date;
}

interface TradeToastProps {
  toast: TradeToastData;
  onDismiss: (id: string) => void;
  duration?: number;
}

function TradeToastItem({ toast, onDismiss, duration = 6000 }: TradeToastProps) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(() => onDismiss(toast.id), 300);
    }, duration);
    return () => clearTimeout(timer);
  }, [toast.id, duration, onDismiss]);

  const handleDismiss = () => {
    setExiting(true);
    setTimeout(() => onDismiss(toast.id), 300);
  };

  const config = {
    buy: {
      icon: ArrowUpRight,
      label: "BUY",
      borderColor: "border-profit/40",
      bgColor: "bg-profit/5",
      accentColor: "text-profit",
      glowColor: "shadow-[0_0_20px_rgba(46,229,157,0.15)]",
    },
    sell: {
      icon: ArrowDownRight,
      label: "SELL",
      borderColor: "border-loss/40",
      bgColor: "bg-loss/5",
      accentColor: "text-loss",
      glowColor: "shadow-[0_0_20px_rgba(255,91,110,0.15)]",
    },
    alert: {
      icon: Bell,
      label: "ALERT",
      borderColor: "border-warning/40",
      bgColor: "bg-warning/5",
      accentColor: "text-warning",
      glowColor: "shadow-[0_0_20px_rgba(251,191,36,0.15)]",
    },
    error: {
      icon: Bell,
      label: "ERROR",
      borderColor: "border-loss/40",
      bgColor: "bg-loss/5",
      accentColor: "text-loss",
      glowColor: "shadow-[0_0_20px_rgba(255,91,110,0.15)]",
    },
  }[toast.type];

  const Icon = config.icon;

  return (
    <div
      className={cn(
        "relative w-[calc(100vw-2rem)] sm:w-80 border rounded-cards p-4 backdrop-blur-xl transition-all duration-300",
        "bg-surface/90",
        config.borderColor,
        config.glowColor,
        exiting
          ? "opacity-0 translate-x-8 scale-95"
          : "opacity-100 translate-x-0 scale-100 animate-slide-in"
      )}
    >
      {/* Dismiss button */}
      <button
        onClick={handleDismiss}
        className="absolute top-3 right-3 text-text-muted hover:text-white transition-colors"
      >
        <X size={14} />
      </button>

      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <div
          className={cn(
            "w-7 h-7 rounded-full flex items-center justify-center",
            config.bgColor
          )}
        >
          <Icon size={14} className={config.accentColor} />
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-[10px] font-black tracking-widest uppercase",
              config.accentColor
            )}
          >
            {config.label}
          </span>
          <span className="text-sm font-black text-white">{toast.symbol}</span>
        </div>
      </div>

      {/* Body */}
      <p className="text-xs text-text-secondary leading-relaxed pl-9">
        {toast.message}
      </p>

      {/* Amount + Time */}
      <div className="flex items-center justify-between mt-2 pl-9">
        {toast.amount != null && (
          <span className={cn("text-xs font-mono font-bold", config.accentColor)}>
            {formatCurrency(toast.amount)}
          </span>
        )}
        <span className="text-[10px] text-text-muted font-mono ml-auto">
          {toast.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
          })}
        </span>
      </div>
    </div>
  );
}

// ── Toast Container (manages the stack) ─────────────────────────────

const MAX_VISIBLE = 5;

export interface ToastAPI {
  push: (toast: Omit<TradeToastData, "id" | "timestamp">) => void;
}

export function TradeToastContainer({
  apiRef,
}: {
  apiRef: React.MutableRefObject<ToastAPI | null>;
}) {
  const [toasts, setToasts] = useState<TradeToastData[]>([]);
  const counterRef = useRef(0);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (data: Omit<TradeToastData, "id" | "timestamp">) => {
      counterRef.current += 1;
      const newToast: TradeToastData = {
        ...data,
        id: `toast-${counterRef.current}-${Date.now()}`,
        timestamp: new Date(),
      };
      setToasts((prev) => [...prev.slice(-(MAX_VISIBLE - 1)), newToast]);
    },
    []
  );

  // Expose the push API via ref
  useEffect(() => {
    apiRef.current = { push };
  }, [apiRef, push]);

  return (
    <div className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-[9999] flex flex-col gap-3 pointer-events-none">
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <TradeToastItem toast={toast} onDismiss={dismiss} />
        </div>
      ))}
    </div>
  );
}
