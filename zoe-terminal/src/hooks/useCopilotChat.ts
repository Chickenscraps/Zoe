import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import { useModeContext } from '../lib/mode';
import { useDashboardData } from './useDashboardData';
import { buildContextPack } from '../lib/contextPack';
import type { CopilotMessage } from '../lib/copilotTypes';

/**
 * Copilot chat hook — manages messages, SSE streaming, and Supabase persistence.
 */
export function useCopilotChat() {
  const { mode } = useModeContext();
  const location = useLocation();
  const dashboardData = useDashboardData();
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  // Load history on mount
  useEffect(() => {
    async function loadHistory() {
      try {
        const { data } = await supabase
          .from('copilot_messages')
          .select('*')
          .eq('mode', mode)
          .order('created_at', { ascending: true })
          .limit(50);

        if (data) {
          setMessages(
            data.map(row => ({
              id: row.id,
              role: row.role as 'user' | 'assistant',
              content: row.content,
              created_at: row.created_at,
            })),
          );
        }
      } catch {
        // Table may not exist yet — that's fine
      }
    }
    loadHistory();
  }, [mode]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return;

      // 1. Create user message
      const userMsg: CopilotMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: content.trim(),
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, userMsg]);

      // Persist user message
      supabase
        .from('copilot_messages')
        .insert({
          id: userMsg.id,
          user_id: '292890243852664855',
          role: 'user',
          content: userMsg.content,
          context_page: location.pathname,
          mode,
          created_at: userMsg.created_at,
        })
        .then();

      // 2. Start streaming assistant response
      setIsStreaming(true);
      const assistantId = crypto.randomUUID();
      const assistantMsg: CopilotMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        streaming: true,
      };
      setMessages(prev => [...prev, assistantMsg]);

      const contextPack = buildContextPack(location.pathname, dashboardData);

      try {
        const abort = new AbortController();
        abortRef.current = abort;

        const params = new URLSearchParams({
          message: content.trim(),
          context: contextPack,
        });

        const response = await fetch(`/api/chat/stream?${params}`, {
          signal: abort.signal,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setBackendOnline(true);

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No readable stream');

        const decoder = new TextDecoder();
        let accumulated = '';
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const payload = JSON.parse(line.slice(6));
              if (payload.chunk) {
                accumulated += payload.chunk;
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantId
                      ? { ...m, content: accumulated }
                      : m,
                  ),
                );
              }
              if (payload.done) break;
              if (payload.error) throw new Error(payload.error);
            } catch {
              // ignore parse errors from incomplete chunks
            }
          }
        }

        // Finalize
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? { ...m, streaming: false, content: accumulated || '(no response)' }
              : m,
          ),
        );

        // Persist assistant message
        supabase
          .from('copilot_messages')
          .insert({
            id: assistantId,
            user_id: '292890243852664855',
            role: 'assistant',
            content: accumulated,
            context_page: location.pathname,
            mode,
            created_at: new Date().toISOString(),
          })
          .then();
      } catch (err: any) {
        if (err?.name === 'AbortError') return;
        console.error('Copilot stream error:', err);
        setBackendOnline(false);
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? { ...m, streaming: false, content: 'Backend offline — try again later.' }
              : m,
          ),
        );
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [isStreaming, mode, location.pathname, dashboardData],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  const clearHistory = useCallback(async () => {
    setMessages([]);
    await supabase.from('copilot_messages').delete().eq('mode', mode);
  }, [mode]);

  return {
    messages,
    isStreaming,
    backendOnline,
    sendMessage,
    stopStreaming,
    clearHistory,
  };
}
