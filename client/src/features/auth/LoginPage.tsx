import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import atiLogoFull from '../../assets/ati-logo-full.svg';
import atiLogoFullInverse from '../../assets/ati-logo-full-inverse.svg';
import { Button } from '../../app/components/ui/button';
import { errorCode, errorMessage, getSession } from '../../services/api';
import { DevAccountChooser } from './DevAccountChooser';
import { useDevSignIn, useGoogleExchange } from './hooks';
import './login-backdrop.css';

/* Same callback contract as Mdm Duro: Google -> /login?code=... -> exchange -> session,
   or /login?error=<code>. In development the "Google" step is the account list below. */
const OAUTH_ERRORS: Record<string, string> = {
  oauth_not_configured: 'Google sign-in is not configured on this server.',
  oauth_denied: 'Google sign-in was cancelled.',
  token_exchange_failed: 'Google authentication failed. Please try again.',
  userinfo_failed: 'Could not retrieve your Google profile.',
  domain_not_allowed: 'Only @atimotors.com accounts are allowed.',
  not_onboarded: 'Only managers and admins can sign in. If you should have access, ask an admin.',
  auth_not_configured: 'The server has no sign-in configured. Start it with make dev, which turns the dev sign-in on.',
  invalid_state: 'That sign-in did not start here or took too long. Please try again.',
};

const rise = (ms: number) => ({ animationDelay: `${ms}ms` });

export function LoginPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const exchange = useGoogleExchange();
  const dev = useDevSignIn();

  const [formError, setFormError] = useState('');
  const [chooser, setChooser] = useState(false);

  /** Step 2 of the Google flow: the real callback brings a `code` back to /login. */
  function signInWithCode(code: string) {
    exchange.mutate(code, {
      onSuccess: () => navigate('/', { replace: true }),
      onError: (e) => {
        setParams({}, { replace: true });
        setFormError(OAUTH_ERRORS[errorCode(e) ?? ''] ?? 'Google sign-in failed. Please try again.');
      },
    });
  }

  // React's development mode runs this effect twice. The one-time code works once, so a second trade would fail and
  // its error would hide the first one's success. The ref survives that second run, so the code is traded once.
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;
    if (getSession()) {
      navigate('/', { replace: true });
      return;
    }
    const code = params.get('code');
    const error = params.get('error');
    if (error) {
      setFormError(OAUTH_ERRORS[error] ?? 'Google sign-in failed.');
      setParams({}, { replace: true });
    } else if (code) {
      setParams({}, { replace: true });
      signInWithCode(code);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startGoogle() {
    // In development the server offers a list of accounts in place of Google; a production build goes to Google.
    if (import.meta.env.DEV) setChooser(true);
    else signInWithGoogle();
  }

  /** The real thing: the server sends the browser to Google and Google sends it back to /login with a code. */
  function signInWithGoogle() {
    window.location.href = '/api/auth/google';
  }

  function pickAccount(accountEmail: string) {
    setChooser(false);
    setFormError('');
    dev.mutate(accountEmail, {
      onSuccess: () => navigate('/', { replace: true }),
      onError: (err) => setFormError(OAUTH_ERRORS[errorCode(err) ?? ''] ?? errorMessage(err, 'Sign in failed.')),
    });
  }

  const busy = exchange.isPending || dev.isPending;

  return (
    <div className="login-page">
      {/* Split: the copy on the left and the sign-in card on the right share one vertical centre. Logo in the corner. */}
      <div className="login-brand-panel relative flex min-h-screen flex-col px-6 py-10 min-[821px]:px-16">
        <div className="flex animate-slide-up items-center gap-3" style={rise(100)}>
          <img src={atiLogoFull} alt="Ati" className="h-12 w-auto dark:hidden" />
          <img src={atiLogoFullInverse} alt="Ati" className="hidden h-12 w-auto dark:block" />        </div>
        <div className="my-auto grid items-center gap-12 py-10 min-[821px]:grid-cols-[1fr_500px] min-[821px]:gap-20 min-[821px]:pr-28">
          <div className="animate-slide-up">
            <p className="font-display text-display font-semibold text-ink">
              Your team's work,
              <br />
              <span className="text-brand">at a glance</span>.
            </p>
            <p className="mt-5 max-w-[46ch] text-md text-ink-muted">
              Create and assign tasks, spot what's overdue or blocked, and review work before it's marked Done.
            </p>
          </div>
          {/* A small box of its own over the backdrop. */}
          <div className="w-full rounded-lg border border-line bg-surface p-12 shadow-raised animate-slide-up" style={rise(200)}>
            <div className="mb-8">
              <h1 className="font-display text-lg font-semibold text-ink">Sign in to Work Board</h1>
              <p className="mt-2 text-md text-ink-muted">Use your @atimotors.com account.</p>
            </div>
            <Button type="button" size="lg" className="w-full" onClick={startGoogle} disabled={busy}>
              {busy ? <Spinner /> : 'Continue with Google'}
            </Button>
            {formError && <p role="alert" className="mt-4 text-sm text-danger-ink">{formError}</p>}
          </div>
        </div>
      </div>

      {import.meta.env.DEV && (
        <DevAccountChooser open={chooser} onOpenChange={setChooser} onPick={pickAccount} onGoogle={signInWithGoogle} />
      )}
    </div>
  );
}

function Spinner() {
  return <span aria-hidden className="inline-block size-4 animate-spin rounded-full border-2 border-current/30 border-t-current" />;
}
