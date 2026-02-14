import './style.css';
import {
  createInitialState,
  generateLevel,
  getBaseColor,
  getTargetColor,
  handleCorrectTap,
  handleWrongTap,
  tickTimer,
  isGameOver,
  getResultRank,
  getPercentile,
  generateShareText,
  type GameState,
} from './game';
import { playCorrect, playWrong, playLevelUp, playGameOver } from './sounds';
import { analytics } from './analytics';

// ─── State ───
let state: GameState = createInitialState();
let timerInterval: ReturnType<typeof setInterval> | null = null;
let targetColor = '';
let currentScreen: 'start' | 'game' | 'result' = 'start';

// ─── URL Params ───
const params = new URLSearchParams(window.location.search);
const challengeLevel = params.get('c') ? parseInt(params.get('c')!, 10) : null;

// ─── Render App Shell ───
function renderApp(): void {
  const app = document.getElementById('app')!;
  app.innerHTML = `
    <div class="bg-glow"></div>

    <!-- Start Screen -->
    <div id="screen-start" class="screen active">
      <h1 class="logo fade-up">Chroma</h1>
      <p class="tagline fade-up fade-up-delay-1">How sharp are your eyes?<br/>Find the different shade before time runs out.</p>
      ${challengeLevel ? `
        <div class="challenge-banner fade-up fade-up-delay-2">
          Someone challenged you to beat <strong>Level ${challengeLevel}</strong>!
        </div>
      ` : ''}
      <button id="btn-start" class="btn btn-primary fade-up fade-up-delay-2">Play Now</button>
      <div class="how-to-play fade-up fade-up-delay-3">
        <strong>How to play:</strong> Tap the tile that's a<br/>different shade. Be fast — the clock is ticking!
      </div>
    </div>

    <!-- Game Screen -->
    <div id="screen-game" class="screen">
      <div class="game-header">
        <div class="game-stat">
          <span class="game-stat-label">Level</span>
          <span id="game-level" class="game-stat-value">1</span>
        </div>
        <div class="game-stat">
          <span class="game-stat-label">Score</span>
          <span id="game-score" class="game-stat-value">0</span>
        </div>
        <div class="game-stat">
          <span class="game-stat-label">Time</span>
          <span id="game-time" class="game-stat-value">15.0</span>
        </div>
      </div>
      <div class="timer-bar">
        <div id="timer-bar-fill" class="timer-bar-fill"></div>
      </div>
      <div class="grid-container">
        <div id="game-grid" class="grid"></div>
      </div>
    </div>

    <!-- Result Screen -->
    <div id="screen-result" class="screen">
      <div class="result-card" id="result-card">
        <div id="result-level" class="result-level">0</div>
        <div class="result-level-label">Level Reached</div>
        <div id="result-title" class="result-title"></div>
        <div id="result-description" class="result-description"></div>
        <div class="result-stats">
          <div class="result-stat">
            <span id="result-score" class="result-stat-value">0</span>
            <span class="result-stat-label">Score</span>
          </div>
          <div class="result-stat">
            <span id="result-correct" class="result-stat-value">0</span>
            <span class="result-stat-label">Correct</span>
          </div>
          <div class="result-stat">
            <span id="result-speed" class="result-stat-value">-</span>
            <span class="result-stat-label">Fastest</span>
          </div>
        </div>
        <div id="result-percentile" class="result-percentile"></div>
        <div class="result-actions">
          <button id="btn-share" class="btn btn-share btn-sm">Copy Result & Challenge Link</button>
          <div class="share-row">
            <button id="btn-twitter" class="btn btn-twitter btn-sm">Share on X</button>
            <button id="btn-again" class="btn btn-secondary btn-sm">Play Again</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Level Up Flash -->
    <div id="level-up-flash" class="level-up-flash">
      <span class="level-up-text" id="level-up-text"></span>
    </div>

    <!-- Copied Toast -->
    <div id="copied-toast" class="copied-toast">Copied to clipboard!</div>
  `;

  // Bind events
  document.getElementById('btn-start')!.addEventListener('click', startGame);
  document.getElementById('btn-share')!.addEventListener('click', shareResult);
  document.getElementById('btn-twitter')!.addEventListener('click', shareTwitter);
  document.getElementById('btn-again')!.addEventListener('click', playAgain);
}

// ─── Screen Management ───
function showScreen(name: 'start' | 'game' | 'result'): void {
  currentScreen = name;
  document.querySelectorAll('.screen').forEach((el) => el.classList.remove('active'));
  document.getElementById(`screen-${name}`)!.classList.add('active');
}

// ─── Start Game ───
function startGame(): void {
  state = createInitialState();
  state.isActive = true;
  state.startTime = Date.now();
  state = generateLevel(state);
  targetColor = getTargetColor(state);

  showScreen('game');
  renderGrid();
  updateHUD();
  startTimer();

  analytics.gameStart();
  if (challengeLevel) {
    analytics.challengeOpen(challengeLevel);
  }
}

// ─── Render Grid ───
function renderGrid(): void {
  const grid = document.getElementById('game-grid')!;
  const { gridSize, targetIndex } = state;
  const total = gridSize * gridSize;

  grid.style.gridTemplateColumns = `repeat(${gridSize}, 1fr)`;
  grid.innerHTML = '';

  const base = getBaseColor(state);

  for (let i = 0; i < total; i++) {
    const tile = document.createElement('div');
    tile.className = 'tile';
    tile.style.backgroundColor = i === targetIndex ? targetColor : base;
    tile.dataset.index = String(i);
    tile.addEventListener('click', () => handleTileTap(i, tile));
    grid.appendChild(tile);
  }
}

// ─── Handle Tap ───
function handleTileTap(index: number, tile: HTMLElement): void {
  if (!state.isActive) return;

  if (index === state.targetIndex) {
    // Correct!
    tile.classList.add('correct');
    playCorrect();

    const prevLevel = state.level;
    state = handleCorrectTap(state);

    analytics.levelComplete(state.level - 1, state.score);

    // Show level-up flash on grid size changes
    const newConfig = state.gridSize;
    if (state.level > 1 && getLevelGridSize(state.level) > getLevelGridSize(prevLevel)) {
      showLevelUpFlash(state.level);
      playLevelUp();
    }

    // Generate next level
    state = generateLevel(state);
    targetColor = getTargetColor(state);

    setTimeout(() => {
      renderGrid();
      updateHUD();
    }, 150);
  } else {
    // Wrong!
    tile.classList.add('wrong');
    playWrong();
    state = handleWrongTap(state);
    updateHUD();

    if (isGameOver(state)) {
      endGame();
    }
  }
}

function getLevelGridSize(level: number): number {
  if (level <= 2) return 2;
  if (level <= 5) return 3;
  if (level <= 9) return 4;
  if (level <= 14) return 5;
  if (level <= 20) return 6;
  if (level <= 27) return 7;
  return 8;
}

// ─── Timer ───
function startTimer(): void {
  if (timerInterval) clearInterval(timerInterval);

  const tickRate = 50; // ms
  timerInterval = setInterval(() => {
    if (!state.isActive) return;

    state = tickTimer(state, tickRate / 1000);
    updateTimerDisplay();

    if (isGameOver(state)) {
      endGame();
    }
  }, tickRate);
}

function stopTimer(): void {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

// ─── HUD Updates ───
function updateHUD(): void {
  document.getElementById('game-level')!.textContent = String(state.level);
  document.getElementById('game-score')!.textContent = String(state.score);
  updateTimerDisplay();
}

function updateTimerDisplay(): void {
  const timeEl = document.getElementById('game-time')!;
  const barEl = document.getElementById('timer-bar-fill')!;
  const maxTime = 20;
  const pct = (state.timeLeft / maxTime) * 100;

  timeEl.textContent = state.timeLeft.toFixed(1);
  barEl.style.width = `${Math.max(0, pct)}%`;

  // Color based on urgency
  barEl.classList.remove('low', 'critical');
  if (state.timeLeft <= 3) {
    barEl.classList.add('critical');
    timeEl.style.color = '#f87171';
  } else if (state.timeLeft <= 6) {
    barEl.classList.add('low');
    timeEl.style.color = '#fbbf24';
  } else {
    timeEl.style.color = '';
  }
}

// ─── Level Up Flash ───
function showLevelUpFlash(level: number): void {
  const flash = document.getElementById('level-up-flash')!;
  const text = document.getElementById('level-up-text')!;
  text.textContent = `Level ${level}`;
  flash.classList.remove('show');
  // Force reflow
  void flash.offsetHeight;
  flash.classList.add('show');
  setTimeout(() => flash.classList.remove('show'), 700);
}

// ─── End Game ───
function endGame(): void {
  state.isActive = false;
  stopTimer();
  playGameOver();

  const rank = getResultRank(state.level);
  const percentile = getPercentile(state.level);

  // Update result screen
  document.getElementById('result-level')!.textContent = String(state.level);
  document.getElementById('result-title')!.textContent = `${rank.emoji} ${rank.title}`;
  (document.getElementById('result-title')! as HTMLElement).style.color = rank.color;
  document.getElementById('result-description')!.textContent = rank.description;
  document.getElementById('result-score')!.textContent = String(state.score);
  document.getElementById('result-correct')!.textContent = String(state.correctCount);
  document.getElementById('result-speed')!.textContent =
    state.fastestReaction < Infinity ? `${(state.fastestReaction / 1000).toFixed(2)}s` : '-';
  document.getElementById('result-percentile')!.textContent =
    `Top ${100 - percentile}% of players`;

  showScreen('result');

  analytics.gameOver(state.level, state.score);
  analytics.submitScore(state.level, state.score);
}

// ─── Sharing ───
const SHARE_BASE = 'https://qwdkadwuyejyadwptgfd.supabase.co/storage/v1/object/public/chroma/index.html';

function getShareUrl(): string {
  return `${SHARE_BASE}?c=${state.level}&ref=share`;
}

function shareResult(): void {
  const text = generateShareText(state.level, state.score);
  const url = getShareUrl();
  const fullText = `${text}\n${url}`;

  if (navigator.share) {
    navigator.share({ text: fullText }).catch(() => {
      copyToClipboard(fullText);
    });
  } else {
    copyToClipboard(fullText);
  }

  analytics.shareClick('copy', state.level);
}

function shareTwitter(): void {
  const text = generateShareText(state.level, state.score);
  const url = getShareUrl();
  const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
  window.open(tweetUrl, '_blank');

  analytics.shareClick('twitter', state.level);
}

function copyToClipboard(text: string): void {
  navigator.clipboard.writeText(text).then(() => {
    showToast();
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast();
  });
}

function showToast(): void {
  const toast = document.getElementById('copied-toast')!;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2000);
}

// ─── Play Again ───
function playAgain(): void {
  analytics.playAgain();
  startGame();
}

// ─── Init ───
renderApp();
analytics.pageView();
