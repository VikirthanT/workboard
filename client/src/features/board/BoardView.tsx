import { useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { ChartBar, Eye, Plus, UsersThree } from '@phosphor-icons/react';
import { ErrorBoundary } from '../../app/components/ErrorBoundary';
import { PageLoading } from '../../app/components/PageLoading';
import { Alert } from '../../app/components/ui/alert';
import { Badge } from '../../app/components/ui/badge';
import { Button } from '../../app/components/ui/button';
import { CheckboxField } from '../../app/components/ui/checkbox';
import { EmptyState } from '../../app/components/ui/empty-state';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import { useToast } from '../../app/components/ui/toast';
import { STATUS_LABEL, type BoardFilter, type Me, type Task, type TeamRecord, type Transition } from '../../app/types/types';
import { useCurrentUser } from '../../hooks';
import { errorMessage } from '../../services/api';
import { useTeams } from '../admin';
import { NoTeamPage } from '../team';
import { OrphanBanner } from './components/BoardPanels';
import { FilterMenu } from './components/FilterMenu';
import { KanbanBoard } from './components/KanbanBoard';
import { ReasonDialog } from './components/ReasonDialog';
import { ReportDialog } from './components/ReportDialog';
import { TaskDetailSheet } from './components/TaskDetailSheet';
import { TaskFormDialog } from './components/TaskFormDialog';
import { useBoard, useBoardParams, useMoveTask } from './hooks';

const FILTERS: BoardFilter[] = ['needs_review', 'overdue', 'blocked', 'due_week'];

const STAT_ITEMS = [
  ['todo', 'To Do'],
  ['in_progress', 'In Progress'],
  ['blocked', 'Blocked'],
  ['overdue', 'Overdue'],
  ['done', 'Done'],
] as const;

/**
 * One board per team. `/` is home for everyone and is always a Kanban board: the manager's own (no team: a plain
 * "no team yet" page; an admin who runs no team is sent on to `/boards`, the read-only board of any team).
 * `/boards` (`adminView`) is the admin's read-only look at any team.
 */
export function BoardView({ adminView = false }: { adminView?: boolean }) {
  const { data: me } = useCurrentUser();
  if (!me) return <p className="p-8 text-base text-ink-subtle">Loading your board…</p>;
  if (adminView) return me.isAdmin ? <AdminBoards me={me} /> : <Navigate to="/" replace />;
  // Home is always a Kanban board: a manager's own, or (an admin who runs no team) the admin's read-only board picker.
  if (!me.team) return me.isAdmin ? <Navigate to="/boards" replace /> : <NoTeamPage />;
  return <BoardInner me={me} />;
}

/** Admin only: pick a team (the `?team=` URL param remembers it) and read its board. No actions. */
function AdminBoards({ me }: { me: Me }) {
  const teams = useTeams(true);
  const [params] = useSearchParams();
  const asked = params.get('team');
  if (teams.isError) return <div className="mx-auto max-w-[720px] p-8"><Alert variant="danger" title="Could not load teams">{errorMessage(teams.error)}</Alert></div>;
  if (!teams.data) return <PageLoading label="Loading teams…" />;
  if (teams.data.length === 0) {
    return <div className="mx-auto max-w-[720px] p-8"><EmptyState icon={UsersThree} title="No teams yet" description="Create a team in the Teams portal first." /></div>;
  }
  if (!asked || !teams.data.some((t) => t.id === asked)) {
    // Their own team if they run one, else the first team.
    const pick = teams.data.find((t) => t.id === me.team?.id) ?? teams.data[0];
    return <Navigate to={`/boards?team=${pick.id}`} replace />;
  }
  return <BoardInner me={me} teams={teams.data} />;
}

/** "NPI (Asha Rao)": the team, then the manager who runs it. */
const teamOption = (t: TeamRecord) => `${t.name} (${t.manager?.displayName ?? 'No manager'})`;

function BoardInner({ me, teams }: { me: Me; teams?: TeamRecord[] }) {
  const p = useBoardParams();
  const board = useBoard(p.query);
  const move = useMoveTask();
  const { toast } = useToast();

  const [form, setForm] = useState<{ task?: Task } | null>(null);
  const [pending, setPending] = useState<{ task: Task; transition: Transition } | null>(null);
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [reportOpen, setReportOpen] = useState(false);

  function runTransition(task: Task, tr: Transition) {
    if (tr.needsReason) {
      setReasonError(null);
      setPending({ task, transition: tr });
      return;
    }
    move.mutate(
      { id: task.id, to: tr.to },
      {
        onSuccess: () => toast(`“${task.title}” moved to ${STATUS_LABEL[tr.to]}.`, 'success'),
        onError: (e) => toast(errorMessage(e), 'danger'),
      },
    );
  }

  function confirmReason(note: string, completedOn?: string) {
    if (!pending) return;
    move.mutate(
      { id: pending.task.id, to: pending.transition.to, note, completedOn },
      {
        onSuccess: () => {
          toast(`“${pending.task.title}” moved to ${STATUS_LABEL[pending.transition.to]}.`, 'success');
          setPending(null);
        },
        onError: (e) => setReasonError(errorMessage(e)),
      },
    );
  }

  function rejectDrop(task: Task, to: string) {
    const from = STATUS_LABEL[task.status];
    const target = STATUS_LABEL[to as keyof typeof STATUS_LABEL];
    const hint = task.actions.transitions.length
      ? `From ${from} you can move it to ${task.actions.transitions.map((t) => STATUS_LABEL[t.to]).join(' or ')}.`
      : `You have no moves on it right now.`;
    toast(`Can't move “${task.title}” from ${from} to ${target}. ${hint}`, 'warning');
  }

  // First load only (later loads keep the previous board on screen): wait for the
  // data so the filters, person dropdown and columns appear together, not one by one.
  if (!board.data) {
    return board.isError
      ? <p role="alert" className="p-8 text-base text-danger-ink">{errorMessage(board.error, 'Could not load the board.')}</p>
      : <PageLoading label="Loading board…" />;
  }
  const tasks = board.data.tasks;
  const teamName = board.data.team.name;
  const readOnly = board.data.readOnly;

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 px-6 py-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">{teamName} board</h1>
          <p className="mt-0.5 text-base text-ink-muted">
            {p.query.attention
              ? `Only what needs ${readOnly ? 'attention' : 'you'}: overdue, blocked, waiting in Review, or without an owner.`
              : 'Every task on the team.'}
          </p>
          {readOnly && (
            <p className="mt-1.5 flex items-center gap-1.5 text-sm font-medium text-ink-muted">
              <Eye size={14} aria-hidden />
              Read-only view of {teamName}
              {board.data.team.manager && <span className="font-normal text-ink-subtle">· managed by {board.data.team.manager.displayName}</span>}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {teams && (
            <div className="w-[300px]">
              <Select value={board.data.team.id} onValueChange={p.setTeam}>
                <SelectTrigger aria-label="Team" className="py-2"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {teams.map((t) => <SelectItem key={t.id} value={t.id}>{teamOption(t)}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          <Button variant="outline" onClick={() => setReportOpen(true)}>
            <ChartBar size={14} aria-hidden />
            Report
          </Button>
          {!readOnly && (
            <Button onClick={() => setForm({})}>
              <Plus size={14} aria-hidden />
              Add task
            </Button>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5" aria-label="Task counts">
        {STAT_ITEMS.map(([key, label]) => (
          <div key={key} className="rounded-lg border border-line bg-surface px-4 py-3">
            <dt className="text-sm text-ink-muted">{label}</dt>
            <dd className="font-display text-xl font-semibold text-ink">{board.data.stats[key]}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <CheckboxField
          label={<span className="inline-flex items-center gap-1.5">Needs attention <Badge>{board.data.attentionCount}</Badge></span>}
          checked={p.query.attention}
          onCheckedChange={(c) => p.setAttention(c === true)}
        />

        {board.data.people.length > 0 && (
          <div className="w-[200px]">
            <Select value={p.query.personId ?? 'everyone'} onValueChange={(v) => p.setPerson(v === 'everyone' ? null : v)}>
              <SelectTrigger aria-label="Person" className="py-2"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="everyone">Everyone</SelectItem>
                {board.data.people.map((person) => <SelectItem key={person.id} value={person.id}>{person.displayName}{person.id === me.user.id ? ' (You)' : ''}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}

        <FilterMenu
          options={FILTERS}
          selected={p.query.filters}
          counts={board.data.filterCounts}
          onToggle={p.toggleFilter}
          onClear={p.clearFilters}
        />
      </div>

      <OrphanBanner tasks={board.data.orphans} onOpen={p.openTask} readOnly={readOnly} />

      {board.isError && <p role="alert" className="text-base text-danger-ink">{errorMessage(board.error, 'Could not load the board.')}</p>}

      <ErrorBoundary label="The board">
        <KanbanBoard tasks={tasks} onOpen={p.openTask} onTransition={runTransition} onBlockedDrop={rejectDrop} readOnly={readOnly} />
      </ErrorBoundary>

      <TaskDetailSheet
        taskId={p.taskId}
        me={me}
        readOnly={readOnly}
        onClose={() => p.openTask(null)}
        onEdit={(t) => setForm({ task: t })}
        onTransition={runTransition}
      />
      <TaskFormDialog
        open={!!form}
        me={me}
        task={form?.task}
        defaultAssigneeId={p.query.personId}
        onClose={(saved) => {
          setForm(null);
          if (saved) toast(form?.task ? 'Task updated.' : 'Task added.', 'success');
        }}
      />
      <ReportDialog open={reportOpen} query={p.query} canAllTeams={me.isAdmin} onClose={() => setReportOpen(false)} />
      <ReasonDialog pending={pending} busy={move.isPending} error={reasonError} onCancel={() => setPending(null)} onConfirm={confirmReason} />
    </div>
  );
}
