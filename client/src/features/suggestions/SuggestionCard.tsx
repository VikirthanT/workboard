import { ArrowCounterClockwise, Check, PencilSimple, Quotes, X } from '@phosphor-icons/react';
import { Button } from '../../app/components/ui/button';
import { formatDayWithWeekday } from '../../app/lib/format';
import { cn } from '../../app/lib/utils';
import type { Suggestion } from '../../app/types/types';

interface Props {
  suggestion: Suggestion;
  assigneeName: string;
  selected: boolean;
  busy: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onReject: () => void;
  onRestore: () => void;
}

/* Priority is the card's colour, as on the board: a coloured left edge plus a matching tag. (Copied from the board's
   card on purpose: a shared place for it waits until a third feature needs it.) */
const PRIORITY_STYLE: Record<Suggestion['priority'], { edge: string; tag: string; label: string }> = {
  high: { edge: 'border-l-danger', tag: 'border-danger-border bg-danger-subtle text-danger-ink', label: 'High' },
  medium: { edge: 'border-l-warning', tag: 'border-warning-border bg-warning-subtle text-warning-ink', label: 'Medium' },
  low: { edge: 'border-l-brand', tag: 'border-brand-border bg-brand-subtle text-brand-ink', label: 'Low' },
};

/** One proposed task. A pending one can be selected, edited or rejected; a rejected one can be restored. */
export function SuggestionCard({ suggestion: s, assigneeName, selected, busy, onToggle, onEdit, onReject, onRestore }: Props) {
  const style = PRIORITY_STYLE[s.priority];
  return (
    <article className={cn('flex h-full flex-col gap-3 rounded-lg border border-l-4 border-line bg-surface p-3 shadow-raised', style.edge, s.state !== 'pending' && 'opacity-75')}>
      <p className="text-base font-medium text-ink">{s.title}</p>

      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <span className={cn('inline-flex items-center rounded-sm border px-1.5 py-px text-xs font-semibold leading-[1.5]', style.tag)}>
          {style.label}<span className="sr-only"> priority</span>
        </span>
        {s.state === 'pending' && selected && <span className="text-xs font-semibold text-brand-ink">Selected to add</span>}
        {s.state === 'approved' && <span className="text-xs font-semibold text-success-ink">Added to board</span>}
        {s.state === 'rejected' && <span className="text-xs font-semibold text-ink-subtle">Rejected</span>}
      </div>

      <p className="text-sm text-ink-muted">{s.description}</p>
      {s.subtasks.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-ink-muted">{s.subtasks.map((part) => <li key={part}>{part}</li>)}</ul>
      )}
      {s.relatedTo && <p className="text-sm text-ink-subtle">Related to: {s.relatedTo}</p>}

      <p className="flex gap-1.5 rounded-sm bg-surface-subtle px-2 py-1.5 text-sm text-ink-muted">
        <Quotes size={12} aria-hidden className="mt-1 flex-none" />
        <span>“{s.evidenceQuote}”</span>
      </p>

      <div className="flex items-center justify-between gap-2 text-sm text-ink-subtle">
        <span className="truncate">{assigneeName}</span>
        <span className="tabular-nums">
          {s.startAt && `Start ${formatDayWithWeekday(s.startAt)} · `}
          {s.dueAt ? `Due ${formatDayWithWeekday(s.dueAt)}${s.dueIsDefault ? ' (default)' : ''}` : 'No due date'}
        </span>
      </div>

      {s.state === 'pending' && (
        <div className="mt-auto flex gap-2">
          <Button size="sm" variant="success-outline" aria-pressed={selected} disabled={busy} onClick={onToggle} className={cn(selected && 'bg-success text-success-fg border-success')}>
            <Check size={14} aria-hidden />{selected ? 'Selected' : 'Select'}
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={onEdit}><PencilSimple size={14} aria-hidden />Edit</Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={onReject}><X size={14} aria-hidden />Reject</Button>
        </div>
      )}
      {s.state === 'rejected' && (
        <div className="mt-auto flex gap-2">
          <Button size="sm" variant="outline" disabled={busy} onClick={onRestore}><ArrowCounterClockwise size={14} aria-hidden />Restore</Button>
        </div>
      )}
    </article>
  );
}
