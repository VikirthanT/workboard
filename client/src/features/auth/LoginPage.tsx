import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import atiLogoFull from '../../assets/ati-logo-full.svg';
import atiLogoFullInverse from '../../assets/ati-logo-full-inverse.svg';
import googleMark from '../../assets/google-mark.svg';
import { errorCode, errorMessage, getSession } from '../../services/api';
import { DevAccountChooser } from './DevAccountChooser';
import { LoginPattern } from './LoginPattern';
import { useDevSignIn, useGoogleExchange } from './hooks';
import './login-page.css';

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
  too_many_attempts: 'Too many sign-in attempts. Wait a few minutes and try again.',
};

const GOOGLE_REDIRECT_TIMEOUT_MS = 10_000;

export function LoginPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const exchange = useGoogleExchange();
  const dev = useDevSignIn();

  const [formError, setFormError] = useState('');
  const [chooser, setChooser] = useState(false);
  const [redirecting, setRedirecting] = useState(false);

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
    setChooser(false);
    setFormError('');
    setRedirecting(true);
    window.location.href = '/api/auth/google';
    // If the page is still here after this long, Google or the server is not answering: unlock the button.
    setTimeout(() => {
      setRedirecting(false);
      setFormError('Google is taking too long to respond. Please try again.');
    }, GOOGLE_REDIRECT_TIMEOUT_MS);
  }

  function pickAccount(accountEmail: string) {
    setChooser(false);
    setFormError('');
    dev.mutate(accountEmail, {
      onSuccess: () => navigate('/', { replace: true }),
      onError: (err) => setFormError(OAUTH_ERRORS[errorCode(err) ?? ''] ?? errorMessage(err, 'Sign in failed.')),
    });
  }

  const busy = exchange.isPending || dev.isPending || redirecting;

  return (
    <div className="login-page">
      {/* Copy on the left, sign-in card on the right, the block pattern in the top right corner and the logo bottom left. */}
      <LoginPattern className="login-pattern" />

      <div className="login-copy">
        <h1 className="login-title font-display font-semibold text-ink">
          Your team's work,
          <br />
          <span className="text-brand">at a glance</span>.
        </h1>
        <p className="login-lede text-ink-muted">
          Create and assign tasks, spot what's overdue or blocked, and review work before it's marked Done.
        </p>
      </div>

      <div className="login-card">
        <div className="login-card-head">
          <h2 className="login-card-title font-display font-semibold text-ink">Sign in</h2>
          <p className="login-card-text text-ink-muted">Use your @atimotors.com account.</p>
        </div>
        <button type="button" className="login-google" onClick={startGoogle} disabled={busy}>
          {busy ? (
            <Spinner />
          ) : (
            <>
              <img src={googleMark} alt="" aria-hidden />
              Continue with Google
            </>
          )}
        </button>
        {formError && <p role="alert" className="mt-4 text-sm text-danger-ink">{formError}</p>}
      </div>

      <img src={atiLogoFull} alt="Ati" className="login-logo dark:hidden" />
      <img src={atiLogoFullInverse} alt="Ati" className="login-logo hidden dark:block" />

      {import.meta.env.DEV && (
        <DevAccountChooser open={chooser} onOpenChange={setChooser} onPick={pickAccount} onGoogle={signInWithGoogle} />
      )}
    </div>
  );
}

function Spinner() {
  return <span aria-hidden className="inline-block size-4 animate-spin rounded-full border-2 border-current/30 border-t-current" />;
}
