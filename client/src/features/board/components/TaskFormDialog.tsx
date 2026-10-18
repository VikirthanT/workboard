import { useEffect, useState } from 'react';
import { Button } from '../../../app/components/ui/button';
import { DatePicker } from '../../../app/components/ui/date-picker';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../../app/components/ui/dialog';
import { Input } from '../../../app/components/ui/input';
import { Label } from '../../../app/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../app/components/ui/select';
import { Textarea } from '../../../app/components/ui/textarea';
import { todayISO } from '../../../app/domain/dates';
import { PRIORITIES, type Me, type Task, type TaskInput } from '../../../app/types/types';
import { errorMessage } from '../../../services/api';
import { useCreateTask, useUpdateTask } from '../hooks';

interface Props {
  open: boolean;
  me: Me;
  /** Present when editing. */
  task?: Task;
  /** Preselect the assignee when creating from a team view. */
  defaultAssigneeId?: string | null;
  onClose: (saved?: Task) => void;
}

const EMPTY = { title: '', description: '', priority: 'medium' as TaskInput['priority'], dueAt: '', assigneeId: '' };

/** Create / edit. The assignee is always someone on the manager's team. */
export function TaskFormDialog({ open, me, task, defaultAssigneeId, onClose }: Props) {
  const create = useCreateTask();
  const update = useUpdateTask();
  const [f, setF] = useState(EMPTY);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setError('');
    setF(
      task
        ? { title: task.title, description: task.description, priority: task.priority, dueAt: task.dueAt ?? '', assigneeId: task.assignee.id }
        : { ...EMPTY, assigneeId: me.assignable.some((p) => p.id === defaultAssigneeId) ? defaultAssigneeId! : me.assignable[0]?.id ?? '' },
    );
  }, [open, task, me, defaultAssigneeId]);

  const canPickAssignee = !task || task.actions.canChangeAssignee;
  const busy = create.isPending || update.isPending;
  const set = <K extends keyof typeof EMPTY>(k: K, v: (typeof EMPTY)[K]) => setF((s) => ({ ...s, [k]: v }));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!f.title.trim()) return setError('Give the task a title.');
    const input: TaskInput = { title: f.title.trim(), description: f.description, priority: f.priority, dueAt: f.dueAt || null, assigneeId: f.assigneeId };
    const done = { onSuccess: (t: Task) => onClose(t), onError: (err: unknown) => setError(errorMessage(err)) };
    if (task) update.mutate({ id: task.id, patch: canPickAssignee ? input : { ...input, assigneeId: undefined } }, done);
    else create.mutate(input, done);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogHeader>
            <div>
              <DialogTitle>{task ? 'Edit task' : 'Add task'}</DialogTitle>
              <DialogDescription>
                {task ? 'Changes are logged on the task timeline.' : 'Assign it to someone on your team.'}
              </DialogDescription>
            </div>
          </DialogHeader>
          <DialogBody className="flex flex-col gap-4">
            <div>
              <Label htmlFor="task-title">Title</Label>
              <Input id="task-title" className="mt-2" autoFocus value={f.title} onChange={(e) => set('title', e.target.value)} maxLength={140} />
            </div>
            <div>
              <Label htmlFor="task-desc">Description</Label>
              <Textarea id="task-desc" className="mt-2" value={f.description} onChange={(e) => set('description', e.target.value)} />
            </div>
            {canPickAssignee && (
              <div>
                <Label htmlFor="task-assignee">Assignee</Label>
                <Select value={f.assigneeId} onValueChange={(v) => set('assigneeId', v)}>
                  <SelectTrigger id="task-assignee" className="mt-2"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {me.assignable.map((p) => <SelectItem key={p.id} value={p.id}>{p.displayName}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="task-priority">Priority</Label>
                <Select value={f.priority} onValueChange={(v) => set('priority', v as TaskInput['priority'])}>
                  <SelectTrigger id="task-priority" className="mt-2 h-10 py-0"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="task-due">Due date</Label>
                <DatePicker id="task-due" className="mt-2 h-10" value={f.dueAt} minDate={todayISO()} onChange={(v) => set('dueAt', v)} />
              </div>
            </div>
            {error && <p role="alert" className="text-sm text-danger-ink">{error}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => onClose()}>Cancel</Button>
            <Button type="submit" disabled={busy}>{task ? 'Save changes' : 'Add task'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
