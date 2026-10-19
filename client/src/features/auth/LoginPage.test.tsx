import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage } from './LoginPage';

const h = vi.hoisted(() => ({ session: null as unknown, exchange: vi.fn(), dev: vi.fn() }));
vi.mock('../../services/api', async (orig) => ({ ...(await orig<object>()), getSession: () => h.session }));
vi.mock('./hooks', () => ({
  useGoogleExchange: () => ({ mutate: h.exchange, isPending: false }),
  useDevSignIn: () => ({ mutate: h.dev, isPending: false }),
  useDevAccounts: () => ({ data: [{ email: 'm1@example.test', name: 'Manager One' }], isLoading: false }),
}));

const at = (search = '') =>
  render(
    <MemoryRouter initialEntries={[`/login${search}`]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<p>home page</p>} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => { h.session = null; h.exchange.mockReset(); h.dev.mockReset(); });
afterEach(() => vi.unstubAllEnvs());

describe('LoginPage', () => {
  it.each([
    ['oauth_not_configured', 'Google sign-in is not configured on this server.'],
    ['oauth_denied', 'Google sign-in was cancelled.'],
    ['token_exchange_failed', 'Google authentication failed. Please try again.'],
    ['userinfo_failed', 'Could not retrieve your Google profile.'],
    ['domain_not_allowed', 'Only @atimotors.com accounts are allowed.'],
    ['not_onboarded', 'Only managers and admins can sign in. If you should have access, ask an admin.'],
    ['auth_not_configured', 'The server has no sign-in configured. Start it with make dev, which turns the dev sign-in on.'],
    ['invalid_state', 'That sign-in did not start here or took too long. Please try again.'],
    ['something_new', 'Google sign-in failed.'],
  ])('?error=%s shows its message', async (code, message) => {
    at(`?error=${code}`);
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
  });

  it('shows no error on a plain visit', () => {
    at();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeEnabled();
  });

  it('trades a ?code= once and goes home on success', async () => {
    h.exchange.mockImplementation((_c, o) => o.onSuccess());
    at('?code=abc');
    expect(h.exchange).toHaveBeenCalledTimes(1);
    expect(h.exchange).toHaveBeenCalledWith('abc', expect.anything());
    expect(await screen.findByText('home page')).toBeInTheDocument();
  });

  it('shows the server\'s sign-in error when the trade fails', async () => {
    h.exchange.mockImplementation((_c, o) => o.onError({ response: { data: { detail: { code: 'not_onboarded' } } } }));
    at('?code=abc');
    expect(await screen.findByRole('alert')).toHaveTextContent('Only managers and admins can sign in.');
  });

  it('an already signed-in visitor goes straight home', async () => {
    h.session = { token: 't', email: 'a@example.test', name: 'A' };
    at();
    expect(await screen.findByText('home page')).toBeInTheDocument();
  });

  it('in development the button opens the account chooser, and picking one signs in as them', async () => {
    h.dev.mockImplementation((_e, o) => o.onSuccess());
    at();
    await userEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
    await userEvent.click(await screen.findByRole('button', { name: /Manager One/ }));
    expect(h.dev).toHaveBeenCalledWith('m1@example.test', expect.anything());
    expect(await screen.findByText('home page')).toBeInTheDocument();
  });

  it('outside development there is no chooser: the button goes to Google', async () => {
    vi.stubEnv('DEV', false);
    const loc = { href: '' };
    vi.stubGlobal('location', loc);
    at();
    await userEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(loc.href).toBe('/api/auth/google');
    expect(screen.queryByText('Choose an account')).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
