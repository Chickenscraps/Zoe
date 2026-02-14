import { useMemo, useEffect, useState } from 'react';

/**
 * Lightweight falling sakura petals (CSS-animated DOM elements).
 * 15 petals with randomized position, size, and duration.
 * Respects prefers-reduced-motion (hidden entirely).
 */
export default function SakuraPetals() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const petals = useMemo(() => {
    return Array.from({ length: 15 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      size: 6 + Math.random() * 10,
      duration: 8 + Math.random() * 12,
      delay: Math.random() * 10,
      drift: -20 + Math.random() * 40,
      rotation: Math.random() * 360,
    }));
  }, []);

  if (reducedMotion) return null;

  return (
    <>
      <style>{`
        @keyframes petalFall {
          0% {
            transform: translateY(-20px) translateX(0px) rotate(var(--petal-rot));
            opacity: 0;
          }
          10% {
            opacity: 0.7;
          }
          90% {
            opacity: 0.5;
          }
          100% {
            transform: translateY(100vh) translateX(var(--petal-drift)) rotate(calc(var(--petal-rot) + 360deg));
            opacity: 0;
          }
        }
      `}</style>
      <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 0 }} aria-hidden>
        {petals.map(p => (
          <div
            key={p.id}
            className="absolute rounded-full"
            style={{
              left: `${p.left}%`,
              top: '-20px',
              width: `${p.size}px`,
              height: `${p.size * 0.7}px`,
              background: `radial-gradient(ellipse, #FABBC2 30%, #EFA3A8 70%)`,
              opacity: 0,
              '--petal-drift': `${p.drift}px`,
              '--petal-rot': `${p.rotation}deg`,
              animation: `petalFall ${p.duration}s ${p.delay}s ease-in infinite`,
            } as React.CSSProperties}
          />
        ))}
      </div>
    </>
  );
}
