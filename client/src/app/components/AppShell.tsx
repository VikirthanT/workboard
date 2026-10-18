import { useEffect } from 'react';
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { CaretDown, Eye, ShieldCheck, SignOut, SquaresFour, UsersThree } from '@phosphor-icons/react';
import atiLogoFull from '../../assets/ati-logo-full.svg';
import atiLogoFullInverse from '../../assets/ati-logo-full-inverse.svg';
import { useDevAccounts, useDevSignIn, useSignOut } from '../../features/auth';
import { useCurrentUser } from '../../hooks';
import { getSession, UNAUTHORIZED_EVENT } from '../../services/api';
import { Avatar } from './ui/avatar';
import { ErrorBoundary } from './ErrorBoundary';
import { PageLoading } from './PageLoading';
import { Badge } from './ui/badge';
import { Menu, type MenuItem } from './ui/menu';
import { ThemeToggle } from './ui/theme-toggle';
import { useToast } from './ui/toast';

/** A header shortcut with a count badge; shown only when there is something to act on. */
function CountLink({ to, label, count }: { to: string; label: string; count: number }) {
  if (count <= 0) return null;
  return (
    <Link to={to} className="flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink focus-ring">
      {label} <Badge tone="teal">{count}</Badge>
    </Link>
  );
}

/** Auth guard + shell. The route tree below it assumes a signed-in user. */
export function AppShell() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const qc = useQueryClient();
  const { toast } = useToast();
  const signOut = useSignOut();
  const dev = useDevSignIn();
  const { data: me, isError } = useCurrentUser();
  const accounts = useDevAccounts(import.meta.env.DEV && !!getSession());

  // 401 is handled once in axiosInstance; it only raises this event.
  useEffect(() => {
    const onUnauthorized = () => { qc.clear(); navigate('/login', { replace: true }); };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [navigate, qc]);

  if (!getSession() || isError) return <Navigate to="/login" replace />;
  // Paint the shell once, with the user in it. Rendering it before /me arrives is
  // what made the header pop in and the page jump after sign-in.
  if (!me) return <PageLoading />;

  const items: MenuItem[] = [];
  if (me.isManager) {
    items.push({ label: 'My board', icon: SquaresFour, onClick: () => navigate('/') });
    items.push({ label: 'My team', icon: UsersThree, onClick: () => navigate('/team') });
  }
  if (me.isAdmin) {
    items.push({ label: 'Teams', icon: ShieldCheck, onClick: () => navigate('/admin') });
    // An admin who runs a team has their own board at home, so this one is named for the other teams'.
    items.push({ label: me.team ? 'Other teams’ boards' : 'Team boards', icon: Eye, onClick: () => navigate('/boards') });
  }
  if (import.meta.env.DEV) {
    // Development only: switch user without signing out, from the same list the login page shows.
    items.push({
      label: 'Sign in as…',
      icon: UsersThree,
      onClick: () => {},
      items: (accounts.data ?? [])
        .filter((a) => a.email !== me.user.email)
        .map((a) => ({
          label: a.note ? `${a.name} (refused)` : a.name,
          onClick: () => dev.mutate(a.email, {
            onSuccess: () => { navigate('/', { replace: true }); toast(`Signed in as ${a.name}.`); },
            onError: () => toast(`${a.name} cannot sign in: not a manager or admin.`, 'warning'),
          }),
        })),
    });
  }
  items.push({ label: 'Sign out', icon: SignOut, onClick: () => { signOut(); navigate('/login', { replace: true }); } });

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-40 border-b border-line bg-surface">
        <div className="flex h-14 items-center gap-6 px-6">
          <Link to="/" aria-label="Work Board home" className="flex items-center gap-2.5 focus-ring">
            <img src={atiLogoFull} alt="Ati" className="h-6 w-auto dark:hidden" />
            <img src={atiLogoFullInverse} alt="Ati" className="hidden h-6 w-auto dark:block" />          </Link>

          {/* The logo is the way back to the board. Admin tools live in the user menu, beside the theme toggle. */}
          <div className="ml-auto flex items-center gap-3">
            <CountLink to="/?filter=needs_review" label="Needs review" count={me.counts.needsReview} />
            <ThemeToggle />
            {me && (
              <Menu
                align="end"
                triggerClassName="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-surface-hover"
                header={<><span className="block font-medium">{me.user.displayName}</span><span className="text-sm text-ink-subtle">{me.team ? `${me.team.name} manager` : me.isAdmin ? 'Admin' : 'No team yet'}</span></>}
                trigger={<><Avatar size="md" name={me.user.displayName} /><span className="hidden text-base font-medium text-ink sm:inline">{me.user.displayName}</span><CaretDown size={12} className="text-ink-subtle" aria-hidden /></>}
                items={items}
              />
            )}
          </div>
        </div>
      </header>
      {/* The header stays when a page fails; moving to another page tries again. */}
      <main><ErrorBoundary resetKey={pathname}><Outlet /></ErrorBoundary></main>
    </div>
  );
}
