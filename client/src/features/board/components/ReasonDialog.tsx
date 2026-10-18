import { useEffect, useState } from 'react';
import { Button } from '../../../app/components/ui/button';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../../app/components/ui/dialog';
import { DatePicker } from '../../../app/components/ui/date-picker';
import { Label } from '../../../app/components/ui/label';
import { Textarea } from '../../../app/components/ui/textarea';
import { todayISO } from '../../../app/domain/dates';
import type { Task, Transition } from '../../../app/types/types';

const COPY: Partial<Record<Transition['kind'], { title: string; help: string; cta: string; label?: string }>> = {
  accept: { title: 'Accept and mark Done', help: 'Remarks for the record: what was checked, anything to note.', cta: 'Accept', label: 'Remarks' },
  complete: { title: 'Mark as Done', help: 'Remarks for the record: what was checked, anything to note.', cta: 'Mark done', label: 'Remarks' },
  block: { title: 'Mark as blocked', help: 'What is in the way? It is shown on the card.', cta: 'Mark blocked' },
  send_back: { title: 'Send back for changes', help: 'What needs to change? It is shown on the card.', cta: 'Send back' },
  reopen: { title: 'Reopen task', help: 'Why does this need more work?', cta: 'Reopen' },
  move_back: { title: 'Move back to To Do', help: 'Why is this moving backwards? The reason is kept on the task.', cta: 'Move back' },
};

interface Props {
  pending: { task: Task; transition: Transition } | null;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  /** `completedOn` is sent only when the move is to Done and the day differs from today. */
  onConfirm: (note: string, completedOn?: string) => void;
}

/** Blocked, move-back, send-back and reopen need a reason; accepting or completing needs remarks. Both are stored with the timeline entry. */
export function ReasonDialog({ pending, busy, error, onCancel, onConfirm }: Props) {
  const [note, setNote] = useState('');
  const [completedOn, setCompletedOn] = useState('');
  useEffect(() => { setNote(''); setCompletedOn(todayISO()); }, [pending]);
  const copy = pending ? COPY[pending.transition.kind] : undefined;
  // Late completion: the day the work finished, from the due date (when it has passed) up to today.
  const asksDay = pending?.transition.to === 'done';
  const today = todayISO();

  return (
    <Dialog open={!!pending} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent>
        <form
          className="flex min-h-0 flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            if (note.trim()) onConfirm(note.trim(), asksDay && completedOn && completedOn !== today ? completedOn : undefined);
          }}
        >
          <DialogHeader>
            <div>
              <DialogTitle>{copy?.title}</DialogTitle>
              <DialogDescription>{pending?.task.title}</DialogDescription>
            </div>
          </DialogHeader>
          <DialogBody>
            <Label htmlFor="reason">{copy?.label ?? 'Reason'}<span aria-hidden className="text-danger"> *</span><span className="sr-only"> (required)</span></Label>
            <Textarea id="reason" className="mt-2" autoFocus value={note} onChange={(e) => setNote(e.target.value)} placeholder={copy?.help} maxLength={500} />
            {asksDay && pending && (
              <div className="mt-4">
                <Label htmlFor="completed-on">Completed on</Label>
                <DatePicker
                  id="completed-on"
                  className="mt-2 h-10"
                  value={completedOn}
                  minDate={pending.task.dueAt && pending.task.dueAt <= today ? pending.task.dueAt : undefined}
                  maxDate={today}
                  onChange={setCompletedOn}
                />
              </div>
            )}
            {error && <p role="alert" className="mt-2 text-sm text-danger-ink">{error}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={onCancel}>Cancel</Button>
            <Button type="submit" disabled={!note.trim() || busy}>{copy?.cta}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
