import { useRef, useEffect, useState } from 'react';
import farLayer from '../../assets/sakura/overlays/far_layer.png';
import treeLayer from '../../assets/sakura/overlays/tree_layer.png';
import petalsLayer from '../../assets/sakura/overlays/petals_layer.png';

/**
 * 3-layer parallax background using PixelChill overlay PNGs.
 * Layers shift ±5/10/15px based on cursor position.
 * Respects prefers-reduced-motion (disables parallax, shows static).
 */
export default function ParallaxBackground() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  useEffect(() => {
    if (reducedMotion) return;
    const handleMouse = (e: MouseEvent) => {
      const cx = window.innerWidth / 2;
      const cy = window.innerHeight / 2;
      setOffset({
        x: (e.clientX - cx) / cx,
        y: (e.clientY - cy) / cy,
      });
    };
    window.addEventListener('mousemove', handleMouse, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouse);
  }, [reducedMotion]);

  const layers = [
    { src: farLayer, mult: 5, opacity: 0.4, z: 0 },
    { src: treeLayer, mult: 10, opacity: 0.6, z: 1 },
    { src: petalsLayer, mult: 15, opacity: 0.3, z: 2 },
  ];

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 pointer-events-none overflow-hidden"
      style={{ zIndex: -1 }}
      aria-hidden
    >
      {layers.map(({ src, mult, opacity, z }) => (
        <div
          key={z}
          className="absolute inset-0 pixel-art"
          style={{
            backgroundImage: `url(${src})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            backgroundRepeat: 'no-repeat',
            imageRendering: 'pixelated',
            opacity,
            transform: reducedMotion
              ? 'none'
              : `translate(${offset.x * mult}px, ${offset.y * mult}px)`,
            transition: 'transform 0.15s ease-out',
            zIndex: z,
          }}
        />
      ))}
    </div>
  );
}
