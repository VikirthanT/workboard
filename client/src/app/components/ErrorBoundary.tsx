import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from './ui/button';

interface Props {
  children: ReactNode;
  /** When this changes (the route, say) a shown error is cleared and the children are tried again. */
  resetKey?: string;
  /** Names the panel in the fallback ("The audit log"); leave out for a whole page. */
  label?: string;
}

/** A render error in the children shows this panel instead of blanking the whole page. */
export class ErrorBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Render error:', error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.failed && prev.resetKey !== this.props.resetKey) this.setState({ failed: false });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    const { label } = this.props;
    return (
      <div role="alert" className={label ? 'flex flex-col items-start gap-3 rounded-lg border border-line p-6' : 'mx-auto flex max-w-[720px] flex-col items-start gap-3 p-8'}>
        <h2 className="font-display text-xl font-semibold text-ink">Something went wrong</h2>
        <p className="text-base text-ink-muted">{label ?? 'This page'} could not be shown. Reloading usually fixes it.</p>
        <Button onClick={() => window.location.reload()}>Reload</Button>
      </div>
    );
  }
}
