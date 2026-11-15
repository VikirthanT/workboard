/*
 * Wire shapes: exactly what comes off the network (snake_case). Never import
 * these into components; the mappers in the service files convert them to the
 * frontend types in app/types/types.ts.
 */
/** A person on a task, a timeline entry, the board or a report. The server calls the name `name`. */
export interface WirePersonSummary {
  id: string;
  name: string;
  email: string;
  active: boolean;
}

/** A row of the people directory as the server sends it: GET /me and a team's members (its PersonResponse). */
export interface WireIdentity {
  id: string;
  name: string;
  email: string;
  slack_user_id: string;
  role: string;
  is_admin: boolean;
  active: boolean;
  team_id: string | null;
  team_name: string | null;
  /** Their tasks that are not Done. Only `GET /teams/{id}/members` fills it in. */
  open_task_count?: number | null;
}

/** One line of the dev sign-in list (GET /dev/accounts, served only while the server runs with DEV_AUTH). */
export interface WireDevAccount {
  email: string;
  name: string;
  can_sign_in: boolean;
}

export interface WireTeam {
  id: string;
  name: string;
  manager: WirePersonSummary | null;
  member_count: number;
  standup_channel_id: string | null;
}

export interface WireSuggestion {
  id: string;
  person_id: string;
  title: string;
  description: string;
  kind: string;
  priority: string;
  start_at: string | null;
  due_at: string | null;
  due_is_default: boolean;
  subtasks: string[];
  evidence_quote: string;
  related_to: string | null;
  state: string;
  late_reply: boolean;
  standup_date: string;
  task_id: string | null;
}

export interface WireStandupPost {
  date: string;
  posted_at: string | null;
  late_reply: boolean;
  last_week: string | null;
  this_week: string | null;
  blockers: string | null;
  message: string | null;
}

export interface WireSuggestionsPage {
  standup_channel_id: string | null;
  last_synced_at: string | null;
  standup_problem: string | null;
  people: {
    person: { id: string; name: string; email: string; role: string };
    standup: WireStandupPost | null;
    suggestions: WireSuggestion[];
  }[];
}

export interface WireDirectorySync {
  people: number;
  added: number;
  reactivated: number;
  deactivated: number;
  deactivated_on_a_team: number;
  new_admins: number;
  skipped: number;
}

export interface WireStandupChannel {
  slack_channel_id: string;
  name: string;
}

export interface WireChannelName {
  id: string;
  name: string;
}

export interface WireChannelMembers {
  channel_id: string;
  members: { person: WireIdentity; state: string; team_name: string | null }[];
  not_in_directory: number;
}

/** One page of a longer list (the server's `Page`). */
export interface WirePage<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface WireTransition {
  to: string;
  kind: string;
  label: string;
  needs_reason: boolean;
}

export interface WireTask {
  id: string;
  number: number;
  team_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  due_at: string | null;
  /** Null only if the person row is gone (the server never deletes people, it marks them inactive). */
  creator: WirePersonSummary | null;
  assignee: WirePersonSummary | null;
  support: WirePersonSummary | null;
  project: string | null;
  returned_count: number;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  overdue: boolean;
  due_soon: boolean;
  needs_reassignment: boolean;
  returned: boolean;
  latest_reason: { kind: string; note: string; at: string; actor_name: string } | null;
  actions: {
    can_edit: boolean;
    can_delete: boolean;
    can_change_assignee: boolean;
    can_comment: boolean;
    transitions: WireTransition[];
  };
}

export interface WireActivity {
  id: string;
  task_id: string;
  task_title: string;
  actor: WirePersonSummary | null;
  kind: string;
  source: string;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  note: string | null;
  created_at: string;
}

export interface WireBoardTeam {
  id: string;
  name: string;
  manager: WirePersonSummary | null;
}

export interface WireImportPreviewRow {
  row: number;
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  assignee: string;
  support: string | null;
  project: string | null;
  stage: string | null;
  start_at: string | null;
  due_at: string | null;
}

export interface WireBoard {
  team: WireBoardTeam;
  read_only: boolean;
  tasks: WireTask[];
  column_totals: Record<'todo' | 'in_progress' | 'blocked' | 'review' | 'done', number>;
  people: WirePersonSummary[];
  filter_counts: Record<string, number>;
  attention_count: number;
  stats: Record<'todo' | 'in_progress' | 'blocked' | 'overdue' | 'done', number>;
  orphans: WireTask[];
}

export interface WireReportCounts {
  todo: number;
  in_progress: number;
  blocked: number;
  review: number;
  overdue: number;
  assigned: number;
  done: number;
  returned: number;
  completion_rate: number | null;
  on_time_rate: number | null;
  avg_days_to_close: number | null;
}

export interface WireReportBlock {
  totals: WireReportCounts;
  people: { person: WirePersonSummary; counts: WireReportCounts }[];
}

export interface WireTeamReport {
  all_time: WireReportBlock;
  period: WireReportBlock;
}

/** The admin's report: one row per team, each with its own people, and the total over every team. */
export interface WireTeamRow {
  team: WireBoardTeam;
  counts: WireReportCounts;
  people: { person: WirePersonSummary; counts: WireReportCounts }[];
}

export interface WireTeamsBlock {
  totals: WireReportCounts;
  teams: WireTeamRow[];
}

export interface WireAllTeamsReport {
  all_time: WireTeamsBlock;
  period: WireTeamsBlock;
}

export interface WireTaskDetail {
  task: WireTask;
  timeline: WireActivity[];
}

export interface WireAudit {
  id: string;
  action: string;
  actor_name: string | null;
  person_name: string | null;
  team_name: string | null;
  reason: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface WireSession {
  token: string;
  email: string;
  name: string;
}
