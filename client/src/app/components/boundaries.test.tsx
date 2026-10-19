/* Where the boundaries are wired: a failing page or panel is contained, and the rest of the screen keeps working. */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './AppShell';
import { TeamView } from '../../features/team/TeamView';
import { ErrorBoundary } from './ErrorBoundary';

const h = vi.hoisted(() => ({ me: undefined as unknown }));
vi.mock('../../hooks', () => ({ useCurrentUser: () => ({ data: h.me, isError: false }) }));
vi.mock('../../services/api', async (orig) => ({ ...(await orig<object>()), getSession: () => ({ token: 't', email: 'a@example.test', name: 'A' }) }));
vi.mock('../../features/auth', () => ({
  useDevAccounts: () => ({ data: [] }),
  useDevSignIn: () => ({ mutate: vi.fn() }),
  useSignOut: () => vi.fn(),
}));
vi.mock('./ui/theme-toggle', () => ({ ThemeToggle: () => null }));
vi.mock('./ui/toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock('../../features/team/TeamMembersPanel', () => ({ TeamMembersPanel: () => { throw new Error('boom'); } }));

const me = {
  user: { id: 'u1', displayName: 'Mina Manager', email: 'mina@example.test' },
  isAdmin: false, isManager: true, team: { id: 't1', name: 'Alpha' }, assignable: [], counts: { needsReview: 0 },
};
const quiet = () => vi.spyOn(console, 'error').mockImplementation(() => {}); // React and the boundary both log the error
const Broken = () => { throw new Error('boom'); };

describe('page boundary (AppShell)', () => {
  const app = (start: string) =>
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={[start]}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<p>Home page</p>} />
              <Route path="/bad" element={<><Broken /></>} />
              <Route path="/other" element={<Link to="/">Back</Link>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

  it('a page that throws shows the fallback under the header, which keeps working', async () => {
    quiet();
    h.me = me;
    app('/bad');
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('This page could not be shown. Reloading usually fixes it.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Work Board home' })).toBeInTheDocument();
    expect(screen.getByText('Mina Manager')).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it('going to another page from the header tries again and recovers', async () => {
    quiet();
    h.me = me;
    app('/bad');
    await userEvent.click(screen.getByRole('link', { name: 'Work Board home' }));
    expect(await screen.findByText('Home page')).toBeInTheDocument();
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    vi.restoreAllMocks();
  });
});

describe('panel boundary (My team)', () => {
  it('a failing people list shows "The team list could not be shown" and the page heading stays', () => {
    quiet();
    h.me = me;
    render(<TeamView />);
    expect(screen.getByRole('heading', { name: 'Alpha team' })).toBeInTheDocument();
    expect(screen.getByText('The team list could not be shown. Reloading usually fixes it.')).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});

describe('ErrorBoundary actions', () => {
  it('Reload reloads the page', async () => {
    quiet();
    const reload = vi.fn();
    vi.stubGlobal('location', { ...window.location, reload });
    render(<ErrorBoundary><Broken /></ErrorBoundary>);
    await userEvent.click(screen.getByRole('button', { name: 'Reload' }));
    expect(reload).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('logs the render error so it is not lost', () => {
    const log = quiet();
    render(<ErrorBoundary><Broken /></ErrorBoundary>);
    expect(log).toHaveBeenCalledWith('Render error:', expect.objectContaining({ message: 'boom' }), expect.any(String));
    vi.restoreAllMocks();
  });
});
