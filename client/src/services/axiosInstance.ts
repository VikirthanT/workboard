import axios from 'axios';
import { clearSession, getSession } from './session';

export const UNAUTHORIZED_EVENT = 'workboard:unauthorized';

export const apiClient = axios.create({ baseURL: '/api' });

apiClient.interceptors.request.use((config) => {
  const s = getSession();
  // A request that already names its caller (the dev "Sign in as" check) must not be rewritten as the current user.
  if (!s || (import.meta.env.DEV && config.headers.has('X-Dev-User-Email'))) return config;
  // A session from Google sign-in has a token, sent as a bearer token (in every build, so the real flow can be tried
  // in development). A development sign-in from the account list has none: the server's DEV_AUTH stub names the
  // caller by this header instead, and only a development build ever sends it.
  if (s.token) config.headers.set('Authorization', `Bearer ${s.token}`);
  else if (import.meta.env.DEV) config.headers.set('X-Dev-User-Email', s.email);
  return config;
});

// 401 handling lives here once; the app shell listens and routes to /login.
apiClient.interceptors.response.use(
  (r) => r,
  (err) => {
    const url: string = err.config?.url ?? '';
    if (err.response?.status === 401 && !url.startsWith('/auth/')) {
      clearSession();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    return Promise.reject(err);
  },
);

/** `detail` is a plain string from the mock, `{code, message}` from the server, or a list from FastAPI's own 422. */
type Detail = string | { code?: string; message?: string } | { msg?: string }[] | undefined;
const detailOf = (err: unknown): Detail => (err as { response?: { data?: { detail?: Detail } } })?.response?.data?.detail;

/** The machine-readable reason a request failed (the server's `code`, or the mock's plain string), if there is one. */
export function errorCode(err: unknown): string | undefined {
  const d = detailOf(err);
  if (typeof d === 'string') return d;
  return d && !Array.isArray(d) ? d.code : undefined;
}

/** Best human-readable message from a failed request. */
export function errorMessage(err: unknown, fallback = 'Something went wrong.'): string {
  const d = detailOf(err);
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d[0]?.msg ?? fallback;
  return d?.message ?? (err as { message?: string })?.message ?? fallback;
}
