import { Component, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import SnesButton from './snes/SnesButton';

interface Props {
  children: ReactNode;
  fallbackMessage?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-12 text-center gap-4">
          <AlertTriangle className="w-10 h-10 text-warning" />
          <h2 className="font-pixel text-[0.55rem] uppercase tracking-[0.08em] text-text-primary">
            {this.props.fallbackMessage ?? 'Something went wrong'}
          </h2>
          <p className="text-sm text-text-muted max-w-md">
            {this.state.error?.message ?? 'An unexpected error occurred.'}
          </p>
          <SnesButton variant="secondary" size="sm" onClick={this.handleReset} className="mt-2">
            <RefreshCw className="w-3 h-3 mr-2 inline" /> Try Again
          </SnesButton>
        </div>
      );
    }

    return this.props.children;
  }
}
