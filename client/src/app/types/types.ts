/*
 * Domain model shared by the mock API and the UI. camelCase on the wire: the
 * real backend will serialise the same shapes, so swapping the mock for it is
 * a transport change, not a type change.
 *
 * Two kinds of people: a User signs in (admin or manager); a Person is in the
 * people directory, never signs in, and is only ever an assignee. One team has
 * one manager, a manager runs one team, a person is on at most one team.
 */
import type { ReportCounts } from '../domain/report';

export const STATUSES = ['todo', 'in_progress', 'blocked', 'review', 'done'] as const;
export type Status = (typeof STATUSES)[number];

export const STATUS_LABEL: Record<Status, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  blocked: 'Blocked',
  review: 'Review',
  done: 'Done',
};

export const PRIORITIES = ['low', 'medium', 'high'] as const;
export type Priority = (typeof PRIORITIES)[number];

/** Who can sign in. Not an assignee. */
export interface User {
  id: string;
  email: string;
  displayName: string;
  isAdmin: boolean;
  active: boolean;
}

/** A people-directory person (name, email, Slack ID). Never signs in. `teamId` null = on no team. */
export interface Person {
  id: string;
  displayName: string;
  email: string;
  slackUserId: string;
  teamId: string | null;
  active: boolean;
}

/** `managerId` is a User id; unique across teams, null until the admin sets one. */
export interface Team {
  id: string;
  name: string;
  managerId: string | null;
  active: boolean;
}

/** The three collections every permission rule reads. */
export interface Directory {
  users: readonly User[];
  people: readonly Person[];
  teams: readonly Team[];
}

export type ActivitySource = 'workboard' | 'slack';

export interface StoredTask {
  id: string;
  teamId: string;
  title: string;
  description: string;
  status: Status;
  priority: Priority;
  /** YYYY-MM-DD, local date. */
  dueAt: string | null;
  /** A User (the manager who created it). */
  creatorId: string;
  /** A Person on the team. */
  assigneeId: string;
  returnedCount: number;
  createdAt: string;
  updatedAt: string;
  closedAt: string | null;
}

export type TransitionKind =
  | 'start'
  | 'block'
  | 'resume'
  | 'submit'
  | 'withdraw'
  | 'accept'
  | 'send_back'
  | 'reopen'
  | 'complete'
  | 'move_back';

export interface Transition {
  to: Status;
  kind: TransitionKind;
  label: string;
  needsReason: boolean;
}

export type ActivityKind = 'created' | 'status' | 'edit' | 'reassign' | 'comment';

export interface StoredActivity {
  id: string;
  taskId: string;
  /** A User today; a Person once Slack comments sync in (Phase 2). */
  actorId: string;
  kind: ActivityKind;
  source: ActivitySource;
  field: string | null;
  oldValue: string | null;
  newValue: string | null;
  note: string | null;
  createdAt: string;
}

// ------------------------------------------------------------------ UI types
// What the view layer consumes. The wire shapes (snake_case) live in
// services/backendTypes.ts; the mappers in services/ convert between them.

/** Used for both a task's creator (a user) and its assignee (a person). */
export interface PersonSummary {
  id: string;
  displayName: string;
  email: string;
  active: boolean;
}

export interface TaskActions {
  canEdit: boolean;
  canDelete: boolean;
  canChangeAssignee: boolean;
  canComment: boolean;
  transitions: Transition[];
}

export interface TaskReason {
  kind: 'blocked' | 'sent_back' | 'reopened';
  note: string;
  at: string;
  actorName: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: Status;
  priority: Priority;
  dueAt: string | null;
  creator: PersonSummary;
  assignee: PersonSummary;
  returnedCount: number;
  createdAt: string;
  updatedAt: string;
  closedAt: string | null;
  overdue: boolean;
  dueSoon: boolean;
  needsReassignment: boolean;
  returned: boolean;
  latestReason: TaskReason | null;
  actions: TaskActions;
}

export interface ActivityItem {
  id: string;
  taskId: string;
  taskTitle: string;
  actor: PersonSummary;
  kind: ActivityKind;
  source: ActivitySource;
  field: string | null;
  oldValue: string | null;
  newValue: string | null;
  note: string | null;
  createdAt: string;
}

export interface MyTeam {
  id: string;
  name: string;
  memberCount: number;
  activeMemberCount: number;
}

export interface Me {
  user: User;
  isAdmin: boolean;
  /** True when the user runs an active team. */
  isManager: boolean;
  /** Null: runs no team. Admins can still read every team's board, read-only. */
  team: MyTeam | null;
  /** Active people on the viewer's team: who a task can be assigned to. */
  assignable: PersonSummary[];
  counts: { needsReview: number };
}

export type BoardFilter = 'overdue' | 'due_week' | 'blocked' | 'needs_review';

export interface BoardQuery {
  /** Admins only: which team's board to read. Null means the viewer's own team. */
  teamId: string | null;
  /** Narrow the cards to what needs attention; off (the default) shows every task. */
  attention: boolean;
  personId: string | null;
  filters: BoardFilter[];
}

export type BoardStats = Record<'todo' | 'in_progress' | 'blocked' | 'overdue' | 'done', number>;

/** The team a board belongs to: just what the board header shows. */
export interface BoardTeam {
  id: string;
  name: string;
  manager: PersonSummary | null;
}

export interface Board {
  /** The team this board belongs to. */
  team: BoardTeam;
  /** True when the viewer may only read it (an admin looking at a team they do not run). */
  readOnly: boolean;
  /** Task counts for everything on the team (person applied), ignoring attention and filters. */
  stats: BoardStats;
  tasks: Task[];
  /** People the person dropdown offers: the team's active people. */
  people: PersonSummary[];
  /** How many cards each filter would show in the current view. */
  filterCounts: Partial<Record<BoardFilter, number>>;
  /** How many cards "Needs attention" would show (overdue, blocked, in Review, orphaned). */
  attentionCount: number;
  /** Open tasks whose assignee is inactive or no longer on the team. */
  orphans: Task[];
}

/** Per-person numbers for the team, plus the team total. */
export interface ReportBlock {
  totals: ReportCounts;
  people: { person: PersonSummary; counts: ReportCounts }[];
}

/** Everything ever, and the chosen period, for the people in the board's current view. */
export interface TeamReport {
  allTime: ReportBlock;
  period: ReportBlock;
}

/** One team in the all-teams report: its own numbers and the people under it. */
export interface TeamRow {
  team: BoardTeam;
  counts: ReportCounts;
  people: ReportBlock['people'];
}

export interface TeamsBlock {
  /** Every task in every team. */
  totals: ReportCounts;
  teams: TeamRow[];
}

/** The admin's report across all teams: everything ever, and the chosen period. */
export interface AllTeamsReport {
  allTime: TeamsBlock;
  period: TeamsBlock;
}

export interface TaskDetail {
  task: Task;
  timeline: ActivityItem[];
}

export interface TaskInput {
  title: string;
  description: string;
  priority: Priority;
  dueAt: string | null;
  assigneeId: string;
}

// ------------------------------------------------------------ teams / admin

export interface TeamRecord {
  id: string;
  name: string;
  manager: PersonSummary | null;
  memberCount: number;
}

export type TeamRole = 'member' | 'manager';

/** A person as the identity endpoints send them: team role and the separate admin flag included. */
export interface PersonRecord extends Person {
  teamName: string | null;
  role: TeamRole;
  isAdmin: boolean;
}

/** One line of the access audit log. The names are looked up by the server; null when that person or team is gone. */
export interface AuditEntry {
  id: string;
  /** `team.create`, `member.add`, ... (the server's action names). */
  action: string;
  actorName: string | null;
  personName: string | null;
  teamName: string | null;
  reason: string | null;
  /** Extra facts the server recorded, such as the old and new manager ids. */
  details: Record<string, unknown> | null;
  createdAt: string;
}

/** One page of a longer server list. `total` counts every match, not just this page. */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Session {
  token: string;
  email: string;
  name: string;
}
