import { useState } from 'react';
import { ArrowBendUpLeft, ChatCircle, Clock, PencilSimple, Prohibit, Trash, UserSwitch } from '@phosphor-icons/react';
import { Avatar } from '../../../app/components/ui/avatar';
import { Badge } from '../../../app/components/ui/badge';
import { Button } from '../../../app/components/ui/button';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../../app/components/ui/dialog';
import { Label } from '../../../app/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../app/components/ui/select';
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '../../../app/components/ui/sheet';
import { FilterTabsList, FilterTabsTrigger, Tabs, TabsContent } from '../../../app/components/ui/tabs';
import { Textarea } from '../../../app/components/ui/textarea';
import { useToast } from '../../../app/components/ui/toast';
import { StatusChip } from '../../../app/components/ui/status-chip';
import { formatDateTime, formatDue } from '../../../app/lib/format';
import { STATUS_LABEL, type ActivityItem, type Me, type Task, type Transition } from '../../../app/types/types';
import { errorMessage } from '../../../services/api';
import { useAddComment, useDeleteTask, useTask, useUpdateTask } from '../hooks';

interface Props {
  taskId: string | null;
  me: Me;
  /** An admin reading a team they do not run: no footer actions (the comment box stays, admins may comment). */
  readOnly?: boolean;
  onClose: () => void;
  onEdit: (t: Task) => void;
  onTransition: (t: Task, tr: Transition) => void;
}

/** Plain sentence for one timeline entry. Reasons are shown verbatim beneath it. */
function describeActivity(a: ActivityItem): string {
  const who = a.actor.displayName;
  switch (a.kind) {
    case 'created': return `${who} created the task`;
    case 'status': return `${who} moved it from ${STATUS_LABEL[a.oldValue as Task['status']] ?? a.oldValue} to ${STATUS_LABEL[a.newValue as Task['status']] ?? a.newValue}`;
    case 'edit': return `${who} changed ${a.field}${a.oldValue !== null || a.newValue !== null ? ` from "${a.oldValue ?? 'none'}" to "${a.newValue ?? 'none'}"` : ''}`;
    case 'reassign': return `${who} reassigned it from ${a.oldValue} to ${a.newValue}`;
    case 'comment': return `${who} commented`;
  }
}

function CommentBox({ taskId }: { taskId: string }) {
  const add = useAddComment();
  const { toast } = useToast();
  const [text, setText] = useState('');
  return (
    <form
      className="mt-4 flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim()) return;
        add.mutate({ id: taskId, body: text.trim() }, { onSuccess: () => setText(''), onError: (err) => toast(errorMessage(err), 'danger') });
      }}
    >
      <Label htmlFor="task-comment">Add a comment</Label>
      <Textarea id="task-comment" value={text} onChange={(e) => setText(e.target.value)} placeholder="Share an update or ask a question" maxLength={1000} />
      <Button type="submit" variant="outline" size="sm" className="self-end" disabled={!text.trim() || add.isPending}>Comment</Button>
    </form>
  );
}

/** Conversation and history kept apart: comments open first, the audit trail is one tab away. */
function Discussion({ task, entries }: { task: Task; entries: ActivityItem[] }) {
  const comments = entries.filter((a) => a.kind === 'comment');
  const history = entries.filter((a) => a.kind !== 'comment');
  return (
    <Tabs defaultValue="comments">
      <FilterTabsList aria-label="Comments and timeline">
        <FilterTabsTrigger value="comments" className="inline-flex items-center gap-1.5"><ChatCircle size={14} aria-hidden />Comments<Badge>{comments.length}</Badge></FilterTabsTrigger>
        <FilterTabsTrigger value="timeline" className="inline-flex items-center gap-1.5"><Clock size={14} aria-hidden />Timeline<Badge>{history.length}</Badge></FilterTabsTrigger>
      </FilterTabsList>

      <TabsContent value="comments" className="mt-4">
        {comments.length === 0 ? (
          <p className="text-base text-ink-subtle">No comments yet.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {comments.map((a) => (
              <li key={a.id} className="flex gap-2.5">
                <Avatar size="sm" name={a.actor.displayName} className="mt-0.5" />
                <div className="min-w-0 flex-1">
                  <p className="text-base"><span className="font-medium text-ink">{a.actor.displayName}</span> <span className="text-xs text-ink-subtle tabular-nums">{formatDateTime(a.createdAt)}</span>{a.source === 'slack' && <Badge className="ml-2">Slack</Badge>}</p>
                  <p className="mt-0.5 whitespace-pre-wrap text-base text-ink-muted">{a.note}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
        {task.actions.canComment ? (
          <CommentBox taskId={task.id} />
        ) : (
          task.status === 'done' && <p className="mt-4 text-sm text-ink-subtle">Comments are closed on Done tasks.</p>
        )}
      </TabsContent>

      <TabsContent value="timeline" className="mt-4">
        <ol className="relative flex flex-col gap-4 border-l border-line pl-4">
          {history.map((a) => (
            <li key={a.id} className="relative">
              <span aria-hidden className="absolute -left-[21px] top-1.5 size-1.5 rounded-full bg-ink-subtle" />
              <p className="text-base text-ink">{describeActivity(a)}</p>
              {a.note && <p className="mt-1 rounded-sm bg-surface-subtle px-2 py-1.5 text-sm text-ink-muted">“{a.note}”</p>}
              <p className="mt-0.5 text-xs text-ink-subtle tabular-nums">{formatDateTime(a.createdAt)}</p>
            </li>
          ))}
        </ol>
        
      </TabsContent>
    </Tabs>
  );
}

export function TaskDetailSheet({ taskId, me, readOnly = false, onClose, onEdit, onTransition }: Props) {
  const detail = useTask(taskId);
  const del = useDeleteTask();
  const { toast } = useToast();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [reassign, setReassign] = useState(false);
  const task = detail.data?.task;

  return (
    <Sheet open={!!taskId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent aria-describedby={undefined}>
        {detail.isError ? (
          <>
            <SheetHeader><SheetTitle className="text-md font-semibold text-ink">Task not found</SheetTitle></SheetHeader>
            <SheetBody><p className="text-base text-ink-muted">This task does not exist or you cannot see it.</p></SheetBody>
          </>
        ) : !task ? (
          <>
            <SheetHeader><SheetTitle className="text-md font-semibold text-ink">Loading…</SheetTitle></SheetHeader>
            <SheetBody />
          </>
        ) : (
          <>
            <SheetHeader>
              <SheetTitle className="text-md font-semibold text-ink">{task.title}</SheetTitle>
              <SheetDescription asChild>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <StatusChip status={task.status} />
                  {task.overdue && <Badge className="border-danger-border bg-danger-subtle text-danger-ink">Overdue</Badge>}
                  {task.dueSoon && <Badge className="border-warning-border bg-warning-subtle text-warning-ink">Due soon</Badge>}
                  {task.returned && <Badge tone="teal">Returned{task.returnedCount > 1 ? ` ×${task.returnedCount}` : ''}</Badge>}
                  {task.needsReassignment && <Badge className="border-warning-border bg-warning-subtle text-warning-ink">Needs reassignment</Badge>}
                </div>
              </SheetDescription>
            </SheetHeader>

            <SheetBody className="flex flex-col gap-6">
              {task.latestReason && (
                <div className="rounded-lg border border-line bg-surface-subtle px-3.5 py-3 text-base">
                  <p className="mb-1 flex items-center gap-1.5 font-semibold text-ink">
                    {task.latestReason.kind === 'blocked' ? <Prohibit size={14} aria-hidden /> : <ArrowBendUpLeft size={14} aria-hidden />}
                    {{ blocked: 'Blocked', sent_back: 'Sent back', reopened: 'Reopened' }[task.latestReason.kind]} by {task.latestReason.actorName}
                  </p>
                  <p className="text-ink-muted">{task.latestReason.note}</p>
                </div>
              )}

              {task.description && <p className="whitespace-pre-wrap text-base text-ink-muted">{task.description}</p>}

              <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2.5 text-base">
                <dt className="text-ink-subtle">Assignee</dt>
                <dd className="flex items-center gap-2 text-ink"><Avatar size="sm" name={task.assignee.displayName} />{task.assignee.displayName} ({task.assignee.email}){!task.assignee.active && <span className="text-sm text-warning-ink">(inactive)</span>}</dd>
                <dt className="text-ink-subtle">Created by</dt>
                <dd className="text-ink">{task.creator.displayName} ({task.creator.email})</dd>
                <dt className="text-ink-subtle">Priority</dt>
                <dd className="capitalize text-ink">{task.priority}</dd>
                <dt className="text-ink-subtle">Due</dt>
                <dd className="text-ink tabular-nums">{formatDue(task.dueAt, task.status === 'done')}</dd>
              </dl>

              <Discussion key={task.id} task={task} entries={detail.data!.timeline} />
            </SheetBody>

            {!readOnly && <SheetFooter className="justify-between">
              <div className="flex items-center gap-1">
                {task.status === 'done' && <p className="text-sm text-ink-subtle">Note: Completed tasks cannot be edited.</p>}
                {task.actions.canEdit && <Button variant="ghost" size="sm" onClick={() => onEdit(task)}><PencilSimple size={14} />Edit</Button>}
                {task.actions.canDelete && <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}><Trash size={14} />Delete</Button>}
                {task.actions.canChangeAssignee && <Button variant="ghost" size="sm" onClick={() => setReassign(true)}><UserSwitch size={14} />Reassign</Button>}
              </div>
              {/* Cards move by dragging. The one button is Resume on a blocked task, which has no obvious column to drop on. */}
              <div className="flex flex-wrap justify-end gap-2">
                {task.actions.transitions.filter((tr) => tr.kind === 'resume').map((tr) => (
                  <Button key={tr.to} size="sm" onClick={() => onTransition(task, tr)}>{tr.label}</Button>
                ))}
              </div>
            </SheetFooter>}

            <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
              <DialogContent>
                <DialogHeader><div><DialogTitle>Delete this task?</DialogTitle><DialogDescription>{task.title}</DialogDescription></div></DialogHeader>
                <DialogBody><p className="text-base text-ink-muted">The task and its timeline are removed. This cannot be undone.</p></DialogBody>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button>
                  <Button variant="destructive" disabled={del.isPending} onClick={() => del.mutate(task.id, { onSuccess: () => { setConfirmDelete(false); onClose(); toast('Task deleted.'); }, onError: (e) => toast(errorMessage(e), 'danger') })}>Delete</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <ReassignDialog open={reassign} task={task} me={me} onClose={() => setReassign(false)} />
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function ReassignDialog({ open, task, me, onClose }: { open: boolean; task: Task; me: Me; onClose: () => void }) {
  const update = useUpdateTask();
  const { toast } = useToast();
  const options = me.assignable;
  const [to, setTo] = useState('');

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><div><DialogTitle>Reassign task</DialogTitle><DialogDescription>{task.title}</DialogDescription></div></DialogHeader>
        <DialogBody>
          <Label htmlFor="reassign-to">New assignee</Label>
          <Select value={to} onValueChange={setTo}>
            <SelectTrigger id="reassign-to" className="mt-2"><SelectValue placeholder="Choose a person" /></SelectTrigger>
            <SelectContent>{options.filter((p) => p.id !== task.assignee.id).map((p) => <SelectItem key={p.id} value={p.id}>{p.displayName}</SelectItem>)}</SelectContent>
          </Select>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            disabled={!to || update.isPending}
            onClick={() => update.mutate({ id: task.id, patch: { assigneeId: to } }, { onSuccess: () => { onClose(); setTo(''); toast('Task reassigned.', 'success'); }, onError: (e) => toast(errorMessage(e), 'danger') })}
          >
            Reassign
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
