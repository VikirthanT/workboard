import { useState } from 'react';
import { Button } from '../../app/components/ui/button';
import { Checkbox } from '../../app/components/ui/checkbox';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../app/components/ui/dialog';
import { Label } from '../../app/components/ui/label';
import { Badge } from '../../app/components/ui/badge';
import { DatePicker } from '../../app/components/ui/date-picker';
import { todayISO } from '../../app/domain/dates';
import { formatDayWithWeekday } from '../../app/lib/format';
import { cn } from '../../app/lib/utils';
import type { PersonSuggestions, Suggestion } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { useAddSuggestions } from './hooks';

interface Props {
  teamId: string;
  /** The ticked suggestions, grouped by the person each is for. */
  groups: { person: PersonSuggestions['person']; suggestions: Suggestion[] }[];
  /** The due dates the manager has typed here, by suggestion id. The page keeps them, so closing and reopening the dialog (or a failed Create) does not lose them. */
  dues: Record<string, string>;
  onDueChange: (id: string, due: string) => void;
  onClose: () => void;
  onAdded: (count: number) => void;
}

const TAG: Record<Suggestion['priority'], string> = {
  high: 'border-danger-border bg-danger-subtle text-danger-ink',
  medium: 'border-warning-border bg-warning-subtle text-warning-ink',
  low: 'border-brand-border bg-brand-subtle text-brand-ink',
};

/**
 * The last look before the tasks are created: each ticked suggestion with its details, and a tick to drop any of them.
 * The page mounts it only while it is open, so everything starts ticked and a re-render of the page cannot reset it.
 */
export function AddSuggestionsDialog({ teamId, groups, dues: typed, onDueChange, onClose, onAdded }: Props) {
  const add = useAddSuggestions(teamId);
  const [keep, setKeep] = useState<Set<string>>(() => new Set(groups.flatMap((g) => g.suggestions.map((s) => s.id))));
  // A task needs a due date: the one the manager typed (kept by the page), else the one the suggestion has.
  const dues: Record<string, string> = Object.fromEntries(groups.flatMap((g) => g.suggestions.map((s) => [s.id, typed[s.id] ?? s.dueAt ?? ''])));
  const [error, setError] = useState('');
  const today = todayISO();

  const people = groups.filter((g) => g.suggestions.some((s) => keep.has(s.id))).length;
  const n = keep.size;
  const flip = (id: string, on: boolean) => setKeep((k) => { const next = new Set(k); if (on) next.add(id); else next.delete(id); return next; });
  // Still to fix: no date yet, or a date that has since passed (a task cannot be due in the past).
  const needsDate = (id: string) => !dues[id] || dues[id] < today;
  const missing = [...keep].filter(needsDate).length;

  function create() {
    add.mutate(
      { suggestionIds: [...keep], dueDates: Object.fromEntries([...keep].map((id) => [id, dues[id]])) },
      { onSuccess: () => { onAdded(n); onClose(); }, onError: (err) => setError(errorMessage(err)) },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-[760px]">
        <DialogHeader>
          <div>
            <DialogTitle>Add {n} {n === 1 ? 'task' : 'tasks'}</DialogTitle>
            <DialogDescription>Check each task and untick anything you do not want, then create them.</DialogDescription>
          </div>
        </DialogHeader>
        <p className="px-5 pt-3 text-sm text-ink-muted">
          {n ? `${n} ${n === 1 ? 'task' : 'tasks'} for ${people} ${people === 1 ? 'person' : 'people'}. Create adds them to the board, each assigned to its person.` : 'Nothing is ticked, so nothing will be created.'}
          {missing > 0 && ` ${missing} still ${missing === 1 ? 'needs' : 'need'} a due date: every task must have one.`}
        </p>
        <DialogBody className="flex flex-col gap-4">
          {groups.map(({ person, suggestions }) => (
            <section key={person.id}>
              <p className="flex items-baseline gap-2 text-md font-semibold text-ink">
                {person.displayName}<span className="text-sm font-normal text-ink-subtle">{person.email}</span>
                <Badge>{suggestions.length}</Badge>
              </p>
              <ul className="mt-2 flex flex-col overflow-hidden rounded-lg border border-line">
                {suggestions.map((s) => (
                  <li key={s.id} className="flex items-start gap-3 border-t border-line px-3.5 py-3 first:border-t-0">
                    <Checkbox id={`add-${s.id}`} className="mt-1" checked={keep.has(s.id)} onCheckedChange={(v) => flip(s.id, v === true)} />
                    <Label htmlFor={`add-${s.id}`} className={cn('flex min-w-0 flex-1 cursor-pointer flex-col gap-1 font-normal', !keep.has(s.id) && 'line-through opacity-45')}>
                      <span className="flex items-center justify-between gap-2.5">
                        <span className="text-base font-semibold text-ink">{s.title}</span>
                        <span className={cn('inline-flex flex-none rounded-sm border px-1.5 py-px text-xs font-semibold', TAG[s.priority])}>{s.priority[0].toUpperCase() + s.priority.slice(1)}</span>
                      </span>
                      <span className="text-sm text-ink-muted">{s.description}</span>
                      {s.startAt && <span className="text-xs tabular-nums text-ink-subtle">Start {formatDayWithWeekday(s.startAt)}</span>}
                    </Label>
                    {keep.has(s.id) && (
                      <div className="w-[190px] shrink-0">
                        <Label htmlFor={`due-${s.id}`} className="text-xs">
                          Due date<span aria-hidden className="text-danger"> *</span><span className="sr-only"> (required)</span>
                        </Label>
                        <DatePicker id={`due-${s.id}`} className="mt-1 h-9" value={dues[s.id]} minDate={today} onChange={(v) => onDueChange(s.id, v)} />
                        {needsDate(s.id) && (
                          <p className="mt-1 text-xs text-danger-ink">{dues[s.id] ? 'That date has passed. Choose a new one.' : 'Choose a due date.'}</p>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {error && <p role="alert" className="text-sm text-danger-ink">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!n || missing > 0 || add.isPending} onClick={create}>Create ({n})</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
