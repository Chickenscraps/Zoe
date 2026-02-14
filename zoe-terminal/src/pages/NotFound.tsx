import { Link } from 'react-router-dom';
import SnesWindow from '../components/snes/SnesWindow';
import SnesButton from '../components/snes/SnesButton';
import ParallaxBackground from '../components/snes/ParallaxBackground';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative">
      <ParallaxBackground />
      <div className="w-full max-w-sm relative z-10">
        <SnesWindow variant="focused" title="Error 404">
          <div className="text-center space-y-4">
            <h1 className="font-pixel text-sm uppercase tracking-[0.08em] text-text-primary">
              Page Not Found
            </h1>
            <p className="text-sm text-text-muted">
              The page you're looking for doesn't exist or has been moved.
            </p>
            <Link to="/">
              <SnesButton variant="secondary" size="md" className="mt-4">
                Return Home
              </SnesButton>
            </Link>
          </div>
        </SnesWindow>
      </div>
    </div>
  );
}
