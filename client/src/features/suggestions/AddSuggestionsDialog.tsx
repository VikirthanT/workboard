import { useState } from 'react';
import { Button } from '../../app/components/ui/button';
import { Checkbox } from '../../app/components/ui/checkbox';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../app/components/ui/dialog';
import { Label } from '../../app/components/ui/label';
import { Badge } from '../../app/components/ui/badge';
import { formatDayWithWeekday } from '../../app/lib/format';
import { cn } from '../../app/lib/utils';
import type { PersonSuggestions, Suggestion } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { useAddSuggestions } from './hooks';

interface Props {
  teamId: string;
  /** The ticked suggestions, grouped by the person each is for. */
  groups: { person: PersonSuggestions['person']; suggestions: Suggestion[] }[];
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
export function AddSuggestionsDialog({ teamId, groups, onClose, onAdded }: Props) {
  const add = useAddSuggestions(teamId);
  const [keep, setKeep] = useState<Set<string>>(() => new Set(groups.flatMap((g) => g.suggestions.map((s) => s.id))));
  const [error, setError] = useState('');

  const people = groups.filter((g) => g.suggestions.some((s) => keep.has(s.id))).length;
  const n = keep.size;
  const flip = (id: string, on: boolean) => setKeep((k) => { const next = new Set(k); if (on) next.add(id); else next.delete(id); return next; });

  function create() {
    add.mutate([...keep], { onSuccess: () => { onAdded(n); onClose(); }, onError: (err) => setError(errorMessage(err)) });
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
                      <span className="text-xs tabular-nums text-ink-subtle">
                        {s.startAt && `Start ${formatDayWithWeekday(s.startAt)} · `}{s.dueAt ? `Due ${formatDayWithWeekday(s.dueAt)}` : 'No due date'}
                      </span>
                    </Label>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {error && <p role="alert" className="text-sm text-danger-ink">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!n || add.isPending} onClick={create}>Create ({n})</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
