import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

/**
 * Theme selection. Three states, not two.
 *
 * 'system' is a real state rather than an initial read, because a one-shot
 * `matchMedia` at mount means the app silently stops agreeing with the OS the
 * moment the user flips it at sunset. Anything that resolves 'system' has to
 * keep listening.
 */
export type Theme = 'light' | 'dark' | 'system';

/** What 'system' currently resolves to. This is what components actually read. */
export type ResolvedTheme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'atiui-theme';

const DARK_QUERY = '(prefers-color-scheme: dark)';

function systemPrefersDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia(DARK_QUERY).matches;
}

/**
 * The single place a theme is written to the DOM.
 *
 * A class on <html>, not `data-theme`. Class is what every piece of tooling
 * already looks for — devtools themes, screenshot harnesses, Tailwind's own
 * dark variant — so matching it means less to explain.
 *
 * The inline script in index.html calls the same logic before first paint.
 * That duplication is deliberate: a provider cannot run early enough, and the
 * alternative is a white flash on every load for dark users.
 */
export function applyTheme(resolved: ResolvedTheme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.classList.toggle('dark', resolved === 'dark');
  // Mirrored for the rare consumer that needs to branch in its own CSS.
  root.dataset.theme = resolved;
}

function resolve(theme: Theme): ResolvedTheme {
  if (theme === 'system') return systemPrefersDark() ? 'dark' : 'light';
  return theme;
}

/**
 * The stored choice, or null when there isn't a usable one.
 *
 * Null rather than 'system' on purpose. This used to return 'system' as its
 * fallback, which meant `readStoredTheme() ?? defaultTheme` never fell through
 * — the `defaultTheme` prop was dead code, and `<ThemeProvider
 * defaultTheme="dark">` silently gave you 'system' instead.
 */
function readStoredTheme(): Theme | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
  } catch {
    /* Safari in private mode throws on localStorage. Falling through to the
     * caller's default is correct — a theme is not worth breaking the app over. */
  }
  return null;
}

interface ThemeContextValue {
  /** What the user picked, including 'system'. */
  theme: Theme;
  /** What that currently means. Use this for icons and `aria-*`. */
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
  /** Flips between light and dark, resolving 'system' first. */
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({
  children,
  defaultTheme = 'system',
  storageKey = THEME_STORAGE_KEY,
}: {
  children: React.ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
}) {
  /* Lazy initialiser, not an effect. Reading localStorage in an effect would
   * render one frame of the wrong theme before correcting — visible as a
   * flash even with the inline script in place, because React's first paint
   * happens after the effect. */
  const [theme, setThemeState] = useState<Theme>(
    () => readStoredTheme() ?? defaultTheme
  );

  const resolvedTheme = resolve(theme);

  /* Keep <html> in step. Runs on mount too, which is what makes the class
   * correct after a client-side navigation into an app that ships the
   * provider without the inline script. */
  useEffect(() => {
    applyTheme(resolvedTheme);
  }, [resolvedTheme]);

  /* Follow the OS while the choice is 'system', and stop the moment it is
   * not — an explicit pick must not be overridden by a sunrise. */
  useEffect(() => {
    if (theme !== 'system') return;
    if (typeof window === 'undefined' || !window.matchMedia) return;

    const mq = window.matchMedia(DARK_QUERY);
    const onChange = () => applyTheme(mq.matches ? 'dark' : 'light');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [theme]);

  const setTheme = useCallback(
    (next: Theme) => {
      setThemeState(next);
      try {
        window.localStorage.setItem(storageKey, next);
      } catch {
        /* Persisting is best-effort; the theme still applies for this session. */
      }
    },
    [storageKey]
  );

  const toggleTheme = useCallback(() => {
    /* Resolving first is what makes the toggle feel right: with theme =
     * 'system' on a dark laptop, the first click must go to LIGHT (the
     * opposite of what is on screen), not to 'system' again. */
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  }, [resolvedTheme, setTheme]);

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme, toggleTheme }),
    [theme, resolvedTheme, setTheme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}

/**
 * The pre-paint snippet for index.html. Kept next to the logic it mirrors so
 * the two are edited together.
 *
 * Reads the same storage key and writes the same class, before the stylesheet
 * has painted. Without it a dark-mode user gets a white flash on every load —
 * which reads as "this app is broken" rather than "this app is loading".
 */
export const themeInitScript = `(function(){try{var k='${THEME_STORAGE_KEY}';var s=localStorage.getItem(k);var t=(s==='light'||s==='dark')?s:(window.matchMedia&&window.matchMedia('${DARK_QUERY}').matches?'dark':'light');var r=document.documentElement;r.classList.toggle('dark',t==='dark');r.dataset.theme=t;}catch(e){}})();`;
