import { useEffect, useState } from 'react';
import { Button } from '../../app/components/ui/button';
import { DatePicker } from '../../app/components/ui/date-picker';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../app/components/ui/dialog';
import { Input } from '../../app/components/ui/input';
import { Label } from '../../app/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import { Textarea } from '../../app/components/ui/textarea';
import { todayISO } from '../../app/domain/dates';
import { PRIORITIES, type Suggestion, type SuggestionPatch } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { useEditSuggestion } from './hooks';

interface Props {
  suggestion: Suggestion | null;
  /** The people a task can go to: everyone on the team. */
  assignees: { id: string; displayName: string }[];
  onClose: () => void;
  /** Called after a save, so the card can be ticked for adding. */
  onSaved: (id: string) => void;
}

const Required = () => <><span aria-hidden className="text-danger"> *</span><span className="sr-only"> (required)</span></>;

/** Check or change a suggestion before adding it. Only the fields that changed are sent, so an untouched due date stays the default. */
export function EditSuggestionDialog({ suggestion, assignees, onClose, onSaved }: Props) {
  const edit = useEditSuggestion();
  const [f, setF] = useState({ title: '', description: '', personId: '', priority: 'medium' as Suggestion['priority'], startAt: '', dueAt: '' });
  const [error, setError] = useState('');

  useEffect(() => {
    if (!suggestion) return;
    setError('');
    setF({
      title: suggestion.title, description: suggestion.description, personId: suggestion.personId, priority: suggestion.priority,
      startAt: suggestion.startAt ?? '', dueAt: suggestion.dueAt ?? '',
    });
  }, [suggestion]);

  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((s) => ({ ...s, [k]: v }));
  const ready = !!f.title.trim() && !!f.description.trim() && !!f.personId;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!suggestion || !ready) return;
    const patch: SuggestionPatch = {};
    if (f.title.trim() !== suggestion.title) patch.title = f.title.trim();
    if (f.description.trim() !== suggestion.description) patch.description = f.description.trim();
    if (f.personId !== suggestion.personId) patch.personId = f.personId;
    if (f.priority !== suggestion.priority) patch.priority = f.priority;
    if (f.startAt !== (suggestion.startAt ?? '')) patch.startAt = f.startAt || null;
    if (f.dueAt !== (suggestion.dueAt ?? '')) patch.dueAt = f.dueAt || null;
    const done = () => { onSaved(suggestion.id); onClose(); };
    if (Object.keys(patch).length === 0) return done();
    edit.mutate({ id: suggestion.id, patch }, { onSuccess: done, onError: (err) => setError(errorMessage(err)) });
  }

  return (
    <Dialog open={!!suggestion} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogHeader>
            <div>
              <DialogTitle>Edit suggestion</DialogTitle>
              <DialogDescription>Check the details, then add it to the board.</DialogDescription>
            </div>
          </DialogHeader>
          <DialogBody className="flex flex-col gap-4">
            <div>
              <Label htmlFor="sug-title">Title<Required /></Label>
              <Input id="sug-title" className="mt-2" autoFocus value={f.title} onChange={(e) => set('title', e.target.value)} maxLength={140} />
            </div>
            <div>
              <Label htmlFor="sug-desc">Description<Required /></Label>
              <Textarea id="sug-desc" className="mt-2" rows={4} value={f.description} onChange={(e) => set('description', e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="sug-assignee">Assignee</Label>
                <Select value={f.personId} onValueChange={(v) => set('personId', v)}>
                  <SelectTrigger id="sug-assignee" className="mt-2 h-10 py-0"><SelectValue /></SelectTrigger>
                  <SelectContent>{assignees.map((p) => <SelectItem key={p.id} value={p.id}>{p.displayName}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="sug-priority">Priority</Label>
                <Select value={f.priority} onValueChange={(v) => set('priority', v as Suggestion['priority'])}>
                  <SelectTrigger id="sug-priority" className="mt-2 h-10 py-0"><SelectValue /></SelectTrigger>
                  <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="sug-start">Start date</Label>
                <DatePicker id="sug-start" className="mt-2 h-10" value={f.startAt} onChange={(v) => set('startAt', v)} />
              </div>
              <div>
                <Label htmlFor="sug-due">Due date</Label>
                <DatePicker id="sug-due" className="mt-2 h-10" value={f.dueAt} minDate={todayISO()} onChange={(v) => set('dueAt', v)} />
              </div>
            </div>
            {error && <p role="alert" className="text-sm text-danger-ink">{error}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="outline" disabled={edit.isPending || !ready}>Save and select</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
