import { rateTone, type RateTone, type ReportCounts } from '../../../app/domain/report';

/* One colour language for the whole report. Colour is the signal only when there is something to see:
   a zero count stays quiet. Tokens only, so the dialog follows the theme and the PDF (light) matches. */

const COUNT_KEY = { 'To Do': 'todo', 'In Progress': 'inProgress', 'In Review': 'review', Blocked: 'blocked', Overdue: 'overdue', Done: 'done' } as const;
/* The design system has four hues only (teal, red, green, amber), so states are told apart by badge style as well as hue:
   soft wash for Blocked / In Review, solid fill for Overdue. (Borders, not rings: the PDF capture does not draw box-shadows.) */
const COUNT_BADGE = {
  todo: 'border-line bg-surface-subtle text-ink-muted',
  inProgress: 'border-brand-border bg-brand-subtle text-brand-ink',
  review: 'border-warning-border bg-warning-subtle text-warning-ink',
  blocked: 'border-danger-border bg-danger-subtle text-danger-ink',
  overdue: 'border-danger bg-danger text-danger-fg',
  done: 'border-success-border bg-success-subtle text-success-ink',
} as const;
const RATE_TEXT: Record<RateTone, string> = { good: 'text-success-ink', fair: 'text-warning-ink', poor: 'text-danger-ink', none: 'text-ink-muted' };

/** One report number: a status badge for the task counts (quiet at 0), a coloured figure for the rates, plain for the rest. */
export function ReportValue({ label, counts, text }: { label: string; counts: ReportCounts; text: string }) {
  if (label === 'Completion') return <span className={RATE_TEXT[rateTone(counts.completionRate)]}>{text}</span>;
  if (label === 'On time') return <span className={RATE_TEXT[rateTone(counts.onTimeRate)]}>{text}</span>;
  const key = COUNT_KEY[label as keyof typeof COUNT_KEY];
  if (!key) return <span>{text}</span>;
  const badge = counts[key] > 0 ? COUNT_BADGE[key] : 'border-transparent text-ink-muted';
  return <span className={`inline-block min-w-9 rounded-md border px-2 py-0.5 text-center ${badge}`}>{text}</span>;
}

const pct = (n: number | null) => (n === null ? '–' : `${Math.round(n * 100)}%`);

/** The four numbers a manager reads first. */
export function SummaryTiles({ totals }: { totals: ReportCounts }) {
  const tiles = [
    { label: 'Assigned', value: String(totals.assigned), tone: 'text-ink' },
    { label: 'Done', value: String(totals.done), tone: totals.done > 0 ? 'text-success-ink' : 'text-ink-muted' },
    { label: 'Completion', value: pct(totals.completionRate), tone: RATE_TEXT[rateTone(totals.completionRate)] },
    { label: 'Overdue', value: String(totals.overdue), tone: totals.overdue > 0 ? 'text-danger-ink' : 'text-ink-muted' },
  ];
  return (
    <dl data-pdf-block className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-lg border border-line px-4 py-3">
          <dt className="text-sm text-ink-muted">{t.label}</dt>
          <dd className={`font-display text-xl font-semibold ${t.tone}`}>{t.value}</dd>        </div>
      ))}
    </dl>
  );
}
