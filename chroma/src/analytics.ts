// ─── Analytics & Event Logging ───
// Logs events to Supabase for tracking engagement

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || '';
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

let sessionId: string = '';

function getSessionId(): string {
  if (sessionId) return sessionId;
  // Reuse session ID for the browser tab
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

interface EventPayload {
  session_id: string;
  event: string;
  referrer: string;
  challenge_level: number | null;
  level: number | null;
  score: number | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

async function logEvent(
  event: string,
  data?: { level?: number; score?: number; metadata?: Record<string, unknown> }
): Promise<void> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return;

  const payload: EventPayload = {
    session_id: getSessionId(),
    event,
    referrer: getReferrer(),
    challenge_level: getChallengeLevel(),
    level: data?.level ?? null,
    score: data?.score ?? null,
    metadata: data?.metadata ?? null,
    created_at: new Date().toISOString(),
  };

  try {
    await fetch(`${SUPABASE_URL}/rest/v1/chroma_events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
        Prefer: 'return=minimal',
      },
      body: JSON.stringify(payload),
    });
  } catch {
    // Silently fail - don't break the game
  }
}

async function submitScore(
  level: number,
  score: number,
  nickname?: string
): Promise<void> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return;

  try {
    await fetch(`${SUPABASE_URL}/rest/v1/chroma_leaderboard`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
        Prefer: 'return=minimal',
      },
      body: JSON.stringify({
        session_id: getSessionId(),
        nickname: nickname || 'Anonymous',
        level,
        score,
        created_at: new Date().toISOString(),
      }),
    });
  } catch {
    // Silently fail
  }
}

async function getTopScores(limit = 10): Promise<Array<{ nickname: string; level: number; score: number }>> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return [];

  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/chroma_leaderboard?select=nickname,level,score&order=level.desc,score.desc&limit=${limit}`,
      {
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
        },
      }
    );
    if (!res.ok) return [];
    return await res.json();
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
