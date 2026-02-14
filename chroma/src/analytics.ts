// ─── Analytics & Event Logging ───
// Logs events to Supabase zoe_events table with source="chroma"

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || '';
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

let sessionId: string = '';

function getSessionId(): string {
  if (sessionId) return sessionId;
  const stored = sessionStorage.getItem('chroma_session_id');
  if (stored) {
    sessionId = stored;
    return sessionId;
  }
  sessionId = crypto.randomUUID();
  sessionStorage.setItem('chroma_session_id', sessionId);
  return sessionId;
}

function getReferrer(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get('ref') || params.get('utm_source') || document.referrer || 'direct';
}

function getChallengeLevel(): number | null {
  const params = new URLSearchParams(window.location.search);
  const c = params.get('c');
  return c ? parseInt(c, 10) : null;
}

async function logEvent(
  event: string,
  data?: { level?: number; score?: number; metadata?: Record<string, unknown> }
): Promise<void> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return;

  const metadata = {
    session_id: getSessionId(),
    referrer: getReferrer(),
    challenge_level: getChallengeLevel(),
    level: data?.level ?? null,
    score: data?.score ?? null,
    user_agent: navigator.userAgent,
    screen: `${screen.width}x${screen.height}`,
    ...data?.metadata,
  };

  try {
    await fetch(`${SUPABASE_URL}/rest/v1/zoe_events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
        Prefer: 'return=minimal',
      },
      body: JSON.stringify({
        source: 'chroma',
        type: 'CHROMA',
        subtype: event,
        severity: 'info',
        title: event,
        body: `Chroma: ${event}`,
        metadata,
        mode: 'live',
      }),
    });
  } catch {
    // Silently fail - don't break the game
  }
}

async function submitScore(
  level: number,
  score: number,
  _nickname?: string
): Promise<void> {
  // Submit score as a game_over event with score data
  await logEvent('score_submit', {
    level,
    score,
    metadata: { nickname: _nickname || 'Anonymous' },
  });
}

async function getTopScores(_limit = 10): Promise<Array<{ nickname: string; level: number; score: number }>> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return [];

  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/zoe_events?source=eq.chroma&subtype=eq.score_submit&select=metadata&order=created_at.desc&limit=${_limit}`,
      {
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
        },
      }
    );
    if (!res.ok) return [];
    const rows: Array<{ metadata: { nickname: string; level: number; score: number } }> = await res.json();
    return rows
      .map(r => ({
        nickname: r.metadata?.nickname || 'Anonymous',
        level: r.metadata?.level || 0,
        score: r.metadata?.score || 0,
      }))
      .sort((a, b) => b.level - a.level || b.score - a.score);
  } catch {
    return [];
  }
}

export const analytics = {
  pageView: () => logEvent('page_view'),
  gameStart: () => logEvent('game_start'),
  levelComplete: (level: number, score: number) =>
    logEvent('level_complete', { level, score }),
  gameOver: (level: number, score: number) =>
    logEvent('game_over', { level, score }),
  shareClick: (platform: string, level: number) =>
    logEvent('share_click', { level, metadata: { platform } }),
  challengeOpen: (challengeLevel: number) =>
    logEvent('challenge_open', { level: challengeLevel }),
  playAgain: () => logEvent('play_again'),
  submitScore,
  getTopScores,
  getSessionId,
};
