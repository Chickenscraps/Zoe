// ─── Game Engine ───

export interface GameState {
  level: number;
  score: number;
  timeLeft: number;
  gridSize: number;
  colorDiff: number;
  baseHue: number;
  baseSat: number;
  baseLit: number;
  targetIndex: number;
  isActive: boolean;
  correctCount: number;
  wrongCount: number;
  startTime: number;
  fastestReaction: number;
  lastTapTime: number;
}

export interface LevelConfig {
  gridSize: number;
  colorDiff: number;
}

const INITIAL_TIME = 15;
const TIME_BONUS = 2.5;
const TIME_PENALTY = 3;
const MAX_TIME = 20;

export function getLevelConfig(level: number): LevelConfig {
  // Grid size increases with level
  let gridSize: number;
  if (level <= 2) gridSize = 2;
  else if (level <= 5) gridSize = 3;
  else if (level <= 9) gridSize = 4;
  else if (level <= 14) gridSize = 5;
  else if (level <= 20) gridSize = 6;
  else if (level <= 27) gridSize = 7;
  else gridSize = 8;

  // Color difference decreases with level (harder to spot)
  // Start at 40% difference, decrease to ~3%
  const minDiff = 3;
  const maxDiff = 40;
  const decay = 0.88;
  const colorDiff = Math.max(minDiff, maxDiff * Math.pow(decay, level - 1));

  return { gridSize, colorDiff };
}

export function createInitialState(): GameState {
  return {
    level: 1,
    score: 0,
    timeLeft: INITIAL_TIME,
    gridSize: 2,
    colorDiff: 40,
    baseHue: 0,
    baseSat: 0,
    baseLit: 0,
    targetIndex: 0,
    isActive: false,
    correctCount: 0,
    wrongCount: 0,
    startTime: 0,
    fastestReaction: Infinity,
    lastTapTime: 0,
  };
}

export function generateLevel(state: GameState): GameState {
  const config = getLevelConfig(state.level);
  const totalTiles = config.gridSize * config.gridSize;

  // Random base color (avoid very dark or very light)
  const hue = Math.random() * 360;
  const sat = 50 + Math.random() * 30; // 50-80%
  const lit = 40 + Math.random() * 25; // 40-65%

  // Pick random target tile
  const targetIndex = Math.floor(Math.random() * totalTiles);

  return {
    ...state,
    gridSize: config.gridSize,
    colorDiff: config.colorDiff,
    baseHue: hue,
    baseSat: sat,
    baseLit: lit,
    targetIndex,
    lastTapTime: Date.now(),
  };
}

export function getBaseColor(state: GameState): string {
  return `hsl(${state.baseHue}, ${state.baseSat}%, ${state.baseLit}%)`;
}

export function getTargetColor(state: GameState): string {
  // Shift the lightness by the difficulty amount
  // Randomly lighter or darker
  const direction = Math.random() > 0.5 ? 1 : -1;
  const newLit = Math.max(10, Math.min(90, state.baseLit + state.colorDiff * direction * 0.4));
  // Also slightly shift hue for extra subtlety
  const hueShift = state.colorDiff * 0.15 * (Math.random() > 0.5 ? 1 : -1);
  return `hsl(${state.baseHue + hueShift}, ${state.baseSat}%, ${newLit}%)`;
}

export function handleCorrectTap(state: GameState): GameState {
  const now = Date.now();
  const reaction = now - state.lastTapTime;
  const speedBonus = Math.max(0, Math.floor((3000 - reaction) / 100));
  const levelPoints = state.level * 10 + speedBonus;

  return {
    ...state,
    level: state.level + 1,
    score: state.score + levelPoints,
    timeLeft: Math.min(MAX_TIME, state.timeLeft + TIME_BONUS),
    correctCount: state.correctCount + 1,
    fastestReaction: Math.min(state.fastestReaction, reaction),
  };
}

export function handleWrongTap(state: GameState): GameState {
  return {
    ...state,
    timeLeft: Math.max(0, state.timeLeft - TIME_PENALTY),
    wrongCount: state.wrongCount + 1,
  };
}

export function tickTimer(state: GameState, dt: number): GameState {
  return {
    ...state,
    timeLeft: Math.max(0, state.timeLeft - dt),
  };
}

export function isGameOver(state: GameState): boolean {
  return state.timeLeft <= 0;
}

export interface ResultRank {
  title: string;
  emoji: string;
  description: string;
  color: string;
}

export function getResultRank(level: number): ResultRank {
  if (level <= 3) return {
    title: 'Color Curious',
    emoji: '👀',
    description: 'You see colors, but the subtle shades escape you. Keep training!',
    color: '#94a3b8',
  };
  if (level <= 6) return {
    title: 'Shade Spotter',
    emoji: '🔍',
    description: 'Not bad! You can pick up most color differences. Room to grow!',
    color: '#4ade80',
  };
  if (level <= 10) return {
    title: 'Color Sharp',
    emoji: '🎯',
    description: 'Impressive perception! You see what most people miss.',
    color: '#38bdf8',
  };
  if (level <= 15) return {
    title: 'Eagle Eye',
    emoji: '🦅',
    description: 'Outstanding! Your color vision is sharper than 90% of players.',
    color: '#a855f7',
  };
  if (level <= 20) return {
    title: 'Chroma Master',
    emoji: '👑',
    description: 'Elite-level perception. You see the invisible differences.',
    color: '#f472b6',
  };
  if (level <= 27) return {
    title: 'Pixel Perfect',
    emoji: '💎',
    description: 'Near-superhuman color vision. Are you even real?',
    color: '#fbbf24',
  };
  return {
    title: 'Chromatic God',
    emoji: '🌈',
    description: 'Legendary. Your eyes operate on a different wavelength entirely.',
    color: '#f87171',
  };
}

export function getPercentile(level: number): number {
  // Simulated percentile based on expected distribution
  if (level <= 2) return 20;
  if (level <= 4) return 35;
  if (level <= 6) return 50;
  if (level <= 8) return 65;
  if (level <= 10) return 75;
  if (level <= 13) return 85;
  if (level <= 16) return 90;
  if (level <= 20) return 95;
  if (level <= 25) return 98;
  return 99;
}

export function generateShareText(level: number, score: number): string {
  const rank = getResultRank(level);
  const blocks = generateEmojiGrid(level);
  return `🎨 Chroma - Color Vision Challenge

${rank.emoji} ${rank.title}
Level ${level} | Score ${score}

${blocks}

How sharp are YOUR eyes?`;
}

function generateEmojiGrid(level: number): string {
  // Create a visual representation of the result
  const filled = Math.min(level, 10);
  const empty = 10 - filled;
  return '🟪'.repeat(filled) + '⬛'.repeat(empty);
}
