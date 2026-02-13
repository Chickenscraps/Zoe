import { useEffect, useRef } from 'react';

interface Star {
  x: number;
  y: number;
  z: number;
  pz: number;
}

const STAR_COUNT = 260;
const SPEED = 0.4;
const MAX_DEPTH = 1000;

export default function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let stars: Star[] = [];
    let w = 0;
    let h = 0;

    const resizeHandler = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
      initStars();
    };

    function initStars() {
      stars = [];
      for (let i = 0; i < STAR_COUNT; i++) {
        const z = Math.random() * MAX_DEPTH;
        stars.push({
          x: (Math.random() - 0.5) * w * 3,
          y: (Math.random() - 0.5) * h * 3,
          z,
          pz: z,
        });
      }
    }

    function draw() {
      // Fade trail effect — semi-transparent black fill instead of full clear
      ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
      ctx.fillRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;

      for (const star of stars) {
        star.pz = star.z;
        star.z -= SPEED * 2;

        if (star.z <= 1) {
          star.x = (Math.random() - 0.5) * w * 3;
          star.y = (Math.random() - 0.5) * h * 3;
          star.z = MAX_DEPTH;
          star.pz = MAX_DEPTH;
          continue;
        }

        // Project to screen
        const sx = (star.x / star.z) * 350 + cx;
        const sy = (star.y / star.z) * 350 + cy;

        // Skip if off screen
        if (sx < -20 || sx > w + 20 || sy < -20 || sy > h + 20) continue;

        // Previous position for trail
        const px = (star.x / star.pz) * 350 + cx;
        const py = (star.y / star.pz) * 350 + cy;

        // Depth factor (0 = far, 1 = close)
        const depth = 1 - star.z / MAX_DEPTH;
        const radius = depth * 2.2 + 0.2;

        // Draw trail streak
        const dx = sx - px;
        const dy = sy - py;
        const trailLen = Math.sqrt(dx * dx + dy * dy);
        if (trailLen > 0.8) {
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(sx, sy);
          ctx.strokeStyle = `rgba(180, 200, 255, ${depth * 0.5})`;
          ctx.lineWidth = Math.max(0.4, radius * 0.5);
          ctx.stroke();
        }

        // Draw star point with glow
        ctx.beginPath();
        ctx.arc(sx, sy, radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(220, 230, 255, ${depth * 0.85 + 0.15})`;
        ctx.fill();
      }

      animId = requestAnimationFrame(draw);
    }

    // Respect reduced motion
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mq.matches) return;

    resizeHandler();
    draw();
    window.addEventListener('resize', resizeHandler);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resizeHandler);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{ zIndex: 1 }}
      aria-hidden="true"
    />
  );
}
