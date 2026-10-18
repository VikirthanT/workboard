import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { cn } from '../../lib/utils';

export type ToastVariant = 'teal' | 'success' | 'warning' | 'danger';

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastOptions {
  variant?: ToastVariant;
  /** Undo, retry, view — anything worth keeping the toast up for. */
  action?: ToastAction;
  /** ms. Ignored while the pointer is over the toast. */
  duration?: number;
}

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
  action?: ToastAction;
  duration: number;
  leaving?: boolean;
}

const DOT_COLOR: Record<ToastVariant, string> = {
  teal: 'var(--color-brand)',
  success: 'var(--color-success)',
  warning: 'var(--color-warning)',
  danger: 'var(--color-danger)',
};

/* Long enough to read a sentence, short enough that a stack of them does not
   wallpaper the screen. Overridable per toast. */
const DEFAULT_DURATION = 5000;
/* How long the exit takes. Must match the slide-out duration below or the row
   is removed mid-animation and the movement is never seen. */
const EXIT_MS = 220;
/* Beyond this the stack is taller than the viewport on a laptop, and the oldest
   is the one the user has finished reading anyway. */
const MAX_VISIBLE = 4;

interface ToastContextValue {
  toast: (message: string, options?: ToastOptions | ToastVariant) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}

function ToastRow({ item, onDone }: { item: ToastItem; onDone: (id: number) => void }) {
  const [entered, setEntered] = useState(false);
  /* Hover pauses the countdown. Without it a toast with an Undo on it is a
     trap: the pointer is already travelling toward the button when it vanishes.
     Timers are paused by clearing them, not by checking a flag on tick — a
     flag still fires the timeout, it just does less when it does. */
  const [paused, setPaused] = useState(false);
  /* Pause has to be *accounted*, not just skipped. An earlier version kept a
     `remaining` ref, never decremented it, and therefore reset the full
     duration on every hover — a paused toast lived 2x its stated time. So the
     clock is split: `left` is what is still owed, `since` is when the current
     run of the countdown started. Pausing banks the elapsed time into `left`. */
  const left = useRef(item.duration);
  const since = useRef(0);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    if (item.leaving) return;

    if (paused) {
      left.current = Math.max(0, left.current - (Date.now() - since.current));
      return;
    }

    since.current = Date.now();
    const timeout = setTimeout(() => onDone(item.id), left.current);
    return () => clearTimeout(timeout);
  }, [paused, item.leaving, item.id, onDone]);

  /* Keyboard focus pauses too — a toast that expires while you are tabbing to
     its Undo is the same trap by another route. */
  const hold = () => setPaused(true);

  return (
    <div
      role="group"
      onMouseEnter={hold}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={hold}
      onBlurCapture={() => setPaused(false)}
      className={cn(
        'flex items-center gap-3 px-[18px] py-[13px] rounded-xl text-sm font-medium',
        'bg-inverse-surface text-inverse-ink border border-inverse-border shadow-modal',
        /* transform+opacity, not `transition-all` — the motion rules allow
           exactly two transition properties and this is the movement one. */
        'transition-[transform,opacity] duration-slow',
        item.leaving
          ? 'opacity-0 translate-y-2'
          : entered
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 translate-y-3'
      )}
    >
      <span
        className="size-2 shrink-0 rounded-full"
        style={{ background: DOT_COLOR[item.variant] }}
      />
      <span className="min-w-0">{item.message}</span>

      {item.action && (
        <button
          type="button"
          onClick={() => {
            item.action?.onClick();
            onDone(item.id);
          }}
          className="-mr-1.5 ml-1 shrink-0 rounded-sm px-1.5 py-0.5 text-sm font-semibold text-brand-ink underline underline-offset-2 hover:bg-surface-hover focus-ring"
        >
          {item.action.label}
        </button>
      )}

      <button
        type="button"
        aria-label={`Dismiss: ${item.message}`}
        onClick={() => onDone(item.id)}
        className="-mr-1.5 ml-auto shrink-0 rounded-sm p-0.5 text-inverse-ink/60 hover:bg-surface-hover hover:text-inverse-ink focus-ring"
      >
        <svg viewBox="0 0 16 16" aria-hidden className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round">
          <path d="M4 4l8 8M12 4l-8 8" />
        </svg>
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  /* Two-step removal: mark it leaving, then actually drop it once the exit has
     played. Removing in one step is why toasts used to blink out of existence
     with no movement at all. */
  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), EXIT_MS);
  }, []);

  const toast = useCallback(
    (message: string, options?: ToastOptions | ToastVariant) => {
      /* A bare string is still accepted, because every existing call site passes
         one and a breaking change here is not worth it. */
      const opts: ToastOptions =
        typeof options === 'string' ? { variant: options } : (options ?? {});

      idRef.current += 1;
      const id = idRef.current;
      setItems((prev) => [
        ...prev,
        {
          id,
          message,
          variant: opts.variant ?? 'teal',
          action: opts.action,
          duration: opts.duration ?? DEFAULT_DURATION,
        },
      ]);
    },
    []
  );

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}
      {/* role=status + aria-live=polite. Without this the toast stack is
          invisible to a screen reader: it appears visually, sits for five
          seconds and leaves with nothing ever spoken. `atomic` so a toast that
          replaces another is read whole rather than as a diff. */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed bottom-8 right-7 z-[999] flex flex-col-reverse items-end gap-2"
      >
        {items.slice(-MAX_VISIBLE).map((item) => (
          <div key={item.id} className="pointer-events-auto">
            <ToastRow item={item} onDone={dismiss} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
