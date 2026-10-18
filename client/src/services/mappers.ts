/* wire (snake_case) -> frontend (camelCase). The single boundary between backendTypes and app/types. */
import type {
  ActivityItem, AllTeamsReport, AuditEntry, BoardTeam, Me, Page, PersonRecord, PersonSummary, ReportBlock, Task, TaskReason,
  TeamRecord, TeamReport, TeamsBlock,
} from '../app/types/types';
import type { ReportCounts } from '../app/domain/report';
import type {
  WireActivity, WireAllTeamsReport, WireAudit, WireBoard, WireBoardTeam, WireIdentity, WirePage, WirePersonSummary,
  WireReportBlock, WireReportCounts, WireTask, WireTeam, WireTeamReport, WireTeamsBlock,
} from './backendTypes';

export const mapSummary = (p: WirePersonSummary): PersonSummary => ({ id: p.id, displayName: p.name, email: p.email, active: p.active });

/** A task's owner or a timeline actor can be missing; show a placeholder rather than crash the card. */
const NOBODY: PersonSummary = { id: '', displayName: 'Unassigned', email: '', active: false };
export const mapOwner = (p: WirePersonSummary | null): PersonSummary => (p ? mapSummary(p) : NOBODY);

export const mapBoardTeam = (t: WireBoardTeam): BoardTeam => ({ id: t.id, name: t.name, manager: t.manager ? mapSummary(t.manager) : null });

const mapCounts = (c: WireReportCounts): ReportCounts => ({
  todo: c.todo, inProgress: c.in_progress, blocked: c.blocked, review: c.review, overdue: c.overdue,
  assigned: c.assigned, done: c.done, returned: c.returned,
  completionRate: c.completion_rate, onTimeRate: c.on_time_rate, avgDaysToClose: c.avg_days_to_close,
});
const mapBlock = (b: WireReportBlock): ReportBlock => ({
  totals: mapCounts(b.totals),
  people: b.people.map((p) => ({ person: mapSummary(p.person), counts: mapCounts(p.counts) })),
});
export const mapTeamReport = (r: WireTeamReport): TeamReport => ({ allTime: mapBlock(r.all_time), period: mapBlock(r.period) });

const mapTeamsBlock = (b: WireTeamsBlock): TeamsBlock => ({
  totals: mapCounts(b.totals),
  teams: b.teams.map((row) => ({
    team: mapBoardTeam(row.team),
    counts: mapCounts(row.counts),
    people: row.people.map((p) => ({ person: mapSummary(p.person), counts: mapCounts(p.counts) })),
  })),
});
export const mapAllTeamsReport = (r: WireAllTeamsReport): AllTeamsReport => ({ allTime: mapTeamsBlock(r.all_time), period: mapTeamsBlock(r.period) });

export const mapPerson = (p: WireIdentity): PersonRecord => ({
  id: p.id, displayName: p.name, email: p.email, slackUserId: p.slack_user_id,
  teamId: p.team_id, teamName: p.team_name, active: p.active,
  role: p.role === 'manager' ? 'manager' : 'member', isAdmin: p.is_admin,
});

export const mapTeam = (t: WireTeam): TeamRecord => ({
  id: t.id, name: t.name, manager: t.manager ? mapSummary(t.manager) : null, memberCount: t.member_count,
});

export const mapTask = (t: WireTask): Task => ({
  id: t.id,
  title: t.title,
  description: t.description,
  status: t.status as Task['status'],
  priority: t.priority as Task['priority'],
  dueAt: t.due_at,
  creator: mapOwner(t.creator),
  assignee: mapOwner(t.assignee),
  returnedCount: t.returned_count,
  createdAt: t.created_at,
  updatedAt: t.updated_at,
  closedAt: t.closed_at,
  overdue: t.overdue,
  dueSoon: t.due_soon,
  needsReassignment: t.needs_reassignment,
  returned: t.returned,
  latestReason: t.latest_reason
    ? ({ kind: t.latest_reason.kind, note: t.latest_reason.note, at: t.latest_reason.at, actorName: t.latest_reason.actor_name } as TaskReason)
    : null,
  actions: {
    canEdit: t.actions.can_edit,
    canDelete: t.actions.can_delete,
    canChangeAssignee: t.actions.can_change_assignee,
    canComment: t.actions.can_comment,
    transitions: t.actions.transitions.map((x) => ({
      to: x.to as Task['status'],
      kind: x.kind as Task['actions']['transitions'][number]['kind'],
      label: x.label,
      needsReason: x.needs_reason,
    })),
  },
});

export const mapActivity = (a: WireActivity): ActivityItem => ({
  id: a.id,
  taskId: a.task_id,
  taskTitle: a.task_title,
  actor: mapOwner(a.actor),
  kind: a.kind as ActivityItem['kind'],
  source: a.source as ActivityItem['source'],
  field: a.field,
  oldValue: a.old_value,
  newValue: a.new_value,
  note: a.note,
  createdAt: a.created_at,
});

/** True when the signed-in person runs a team: the only case that has a board of their own to act on. */
export const runsTeam = (self: WireIdentity): boolean => self.active && self.role === 'manager' && self.team_id !== null;

/**
 * Build `Me` from the real API: GET /me, the team's people, and the board (for the "needs review" count).
 * The manager is on the team's list as an assignee, but does not count toward "people on the team": a manager
 * whose team has nobody else is sent to My team first.
 */
export function mapRealMe(self: WireIdentity, members: WireIdentity[], board: Pick<WireBoard, 'tasks'> | null): Me {
  const mine = runsTeam(self);
  const others = members.filter((m) => m.role !== 'manager');
  return {
    user: { id: self.id, email: self.email, displayName: self.name, isAdmin: self.is_admin, active: self.active },
    isAdmin: self.is_admin,
    isManager: mine,
    team: mine
      ? { id: self.team_id!, name: self.team_name ?? '', memberCount: others.length, activeMemberCount: others.filter((m) => m.active).length }
      : null,
    assignable: mine ? members.filter((m) => m.active).map(mapSummary) : [],
    counts: { needsReview: board ? board.tasks.filter((t) => t.status === 'review').length : 0 },
  };
}

export const mapAudit = (a: WireAudit): AuditEntry => ({
  id: a.id,
  action: a.action,
  actorName: a.actor_name,
  personName: a.person_name,
  teamName: a.team_name,
  reason: a.reason,
  details: a.details,
  createdAt: a.created_at,
});

export const mapPage = <W, T>(p: WirePage<W>, map: (w: W) => T): Page<T> => ({ items: p.items.map(map), total: p.total, limit: p.limit, offset: p.offset });
