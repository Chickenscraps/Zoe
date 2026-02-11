/**
 * Chime — Web Audio API synthesized notification sounds.
 *
 * Zero dependencies. Generates short tonal chimes using oscillators
 * and gain envelopes. All sounds are procedural (no audio files needed).
 */

let audioCtx: AudioContext | null = null;

function getCtx(): AudioContext {
  if (!audioCtx) {
    audioCtx = new AudioContext();
  }
  // Resume if suspended (browsers block autoplay until user gesture)
  if (audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

/** Play a short tone at the given frequency with a fade-out envelope. */
function playTone(
  freq: number,
  duration: number,
  type: OscillatorType = "sine",
  volume = 0.25
) {
  const ctx = getCtx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = type;
  osc.frequency.setValueAtTime(freq, ctx.currentTime);

  gain.gain.setValueAtTime(volume, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start(ctx.currentTime);
  osc.stop(ctx.currentTime + duration);
}

// ── Public chime functions ──────────────────────────────────────────

/** Buy chime — ascending two-note arpeggio (positive, hopeful). */
export function chimeBuy() {
  playTone(523.25, 0.15, "sine", 0.2);   // C5
  setTimeout(() => {
    playTone(659.25, 0.25, "sine", 0.2);  // E5
  }, 100);
  setTimeout(() => {
    playTone(783.99, 0.35, "sine", 0.15); // G5
  }, 200);
}

/** Sell chime — descending two-note (resolved, complete). */
export function chimeSell() {
  playTone(783.99, 0.15, "sine", 0.2);   // G5
  setTimeout(() => {
    playTone(523.25, 0.35, "sine", 0.2);  // C5
  }, 120);
}

/** Alert chime — single attention-getting ping. */
export function chimeAlert() {
  playTone(880, 0.3, "triangle", 0.2);    // A5 triangle wave
}

/** Error chime — low warning tone. */
export function chimeError() {
  playTone(220, 0.4, "sawtooth", 0.1);    // A3 sawtooth
}

/**
 * Initialize the audio context on first user interaction.
 * Call this once (e.g., on a click handler) to unlock autoplay.
 */
export function initAudio() {
  getCtx();
}
