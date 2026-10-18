import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ErrorBoundary } from './ErrorBoundary';

afterEach(cleanup);

function Broken(): never {
  throw new Error('boom');
}

describe('ErrorBoundary', () => {
  it('shows the fallback for a child that throws, and the rest of the page still renders', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {}); // React and the boundary both log the error
    render(
      <div>
        <header>Header stays</header>
        <ErrorBoundary><Broken /></ErrorBoundary>
      </div>,
    );

    expect(screen.getByText('Something went wrong')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Reload' })).toBeTruthy();
    expect(screen.getByText('Header stays')).toBeTruthy();
    vi.restoreAllMocks();
  });

  it('names the panel that failed and leaves the panels beside it alone', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <div>
        <ErrorBoundary label="The audit log"><Broken /></ErrorBoundary>
        <ErrorBoundary label="The admins list"><p>Admins fine</p></ErrorBoundary>
      </div>,
    );

    expect(screen.getByText('The audit log could not be shown. Reloading usually fixes it.')).toBeTruthy();
    expect(screen.getByText('Admins fine')).toBeTruthy();
    vi.restoreAllMocks();
  });

  it('renders its children when nothing throws', () => {
    render(<ErrorBoundary><p>All fine</p></ErrorBoundary>);

    expect(screen.getByText('All fine')).toBeTruthy();
    expect(screen.queryByText('Something went wrong')).toBeNull();
  });

  it('tries the children again when the reset key changes', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    let broken = true;
    const Maybe = () => (broken ? <Broken /> : <p>Recovered</p>);
    const { rerender } = render(<ErrorBoundary resetKey="/a"><Maybe /></ErrorBoundary>);
    expect(screen.getByText('Something went wrong')).toBeTruthy();

    broken = false;
    rerender(<ErrorBoundary resetKey="/b"><Maybe /></ErrorBoundary>);

    expect(screen.getByText('Recovered')).toBeTruthy();
    vi.restoreAllMocks();
  });
});
