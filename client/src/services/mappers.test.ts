/* Contract test: JSON shaped exactly like the server's responses (server/tasks/schemas.py) goes through the mappers.
   The payloads are synthetic. If the server's shape changes, this is where the client finds out. */
import { describe, expect, it } from 'vitest';
import type { WireActivity, WireBoardTeam, WireIdentity, WireTask } from './backendTypes';
import { mapActivity, mapBoardTeam, mapRealMe, mapTask, runsTeam } from './mappers';

const ravi = { id: 'p-ravi', name: 'Ravi', email: 'ravi@atimotors.com', active: true };
const asha = { id: 'p-asha', name: 'Asha', email: 'asha@atimotors.com', active: true };

const serverTask = (over: Partial<WireTask> = {}): WireTask => ({
  id: 't1', team_id: 'team1', title: 'Wire harness', description: '', status: 'blocked', priority: 'high', due_at: '2026-10-30',
  creator: asha, assignee: ravi, returned_count: 0,
  created_at: '2026-10-17T08:00:00Z', updated_at: '2026-10-17T09:00:00Z', closed_at: null,
  overdue: false, due_soon: true, needs_reassignment: false, returned: false,
  latest_reason: { kind: 'blocked', note: 'waiting on supplier', at: '2026-10-17T09:00:00Z', actor_name: 'Asha' },
  actions: {
    can_edit: true, can_delete: false, can_change_assignee: true, can_comment: true,
    transitions: [{ to: 'in_progress', kind: 'resume', label: 'Resume', needs_reason: false }],
  },
  ...over,
});

describe('server task -> client task', () => {
  it('maps people by their `name`, the reason, and the actions the server allows', () => {
    const task = mapTask(serverTask());

    expect(task.assignee.displayName).toBe('Ravi');
    expect(task.creator.displayName).toBe('Asha');
    expect(task.latestReason).toEqual({ kind: 'blocked', note: 'waiting on supplier', at: '2026-10-17T09:00:00Z', actorName: 'Asha' });
    expect(task.actions.transitions).toEqual([{ to: 'in_progress', kind: 'resume', label: 'Resume', needsReason: false }]);
    expect(task.dueSoon).toBe(true);
  });

  it('shows a placeholder instead of crashing when the assignee is missing', () => {
    const task = mapTask(serverTask({ assignee: null, needs_reassignment: true }));

    expect(task.assignee).toEqual({ id: '', displayName: 'Unassigned', email: '', active: false });
    expect(task.needsReassignment).toBe(true);
  });
});

describe('server timeline entry and board team', () => {
  it('maps a comment whose actor is gone', () => {
    const entry: WireActivity = {
      id: 'a1', task_id: 't1', task_title: 'Wire harness', actor: null, kind: 'comment', source: 'workboard',
      field: null, old_value: null, new_value: null, note: 'Parts arrive Monday', created_at: '2026-10-17T10:00:00Z',
    };

    const item = mapActivity(entry);

    expect(item.actor.displayName).toBe('Unassigned');
    expect(item.note).toBe('Parts arrive Monday');
  });

  it('maps the slim board team, with or without a manager', () => {
    const team: WireBoardTeam = { id: 'team1', name: 'NPI', manager: asha };

    expect(mapBoardTeam(team)).toEqual({ id: 'team1', name: 'NPI', manager: { id: 'p-asha', displayName: 'Asha', email: 'asha@atimotors.com', active: true } });
    expect(mapBoardTeam({ ...team, manager: null }).manager).toBeNull();
  });
});

const person = (over: Partial<WireIdentity>): WireIdentity => ({
  id: 'p1', name: 'Asha', email: 'asha@atimotors.com', slack_user_id: 'U1', role: 'member', is_admin: false, active: true,
  team_id: null, team_name: null, ...over,
});
const manager = person({ role: 'manager', team_id: 'team1', team_name: 'NPI' });
const reviewing = { tasks: [{ status: 'review' }, { status: 'review' }, { status: 'todo' }] as WireTask[] };

describe('Me from the real API (GET /me + the team + the board)', () => {
  it('a manager gets their team, the people they can assign to (themselves included) and the review count', () => {
    const members = [manager, person({ id: 'p2', name: 'Ravi', email: 'ravi@atimotors.com' }), person({ id: 'p3', name: 'Zoe', active: false })];

    const me = mapRealMe(manager, members, reviewing);

    expect(me.isManager).toBe(true);
    expect(me.team).toEqual({ id: 'team1', name: 'NPI', memberCount: 2, activeMemberCount: 1 }); // the manager is not counted
    expect(me.assignable.map((p) => p.displayName)).toEqual(['Asha', 'Ravi']); // active only
    expect(me.counts.needsReview).toBe(2);
  });

  it('a manager whose team has nobody else reads as having no active people, so they are sent to My team', () => {
    const me = mapRealMe(manager, [manager], { tasks: [] });

    expect(me.team?.activeMemberCount).toBe(0);
    expect(me.assignable).toHaveLength(1);
  });

  it('an admin with no team has no board of their own, no assignees and a zero count', () => {
    const admin = person({ is_admin: true });

    const me = mapRealMe(admin, [], null);

    expect(me).toMatchObject({ isAdmin: true, isManager: false, team: null, assignable: [], counts: { needsReview: 0 } });
    expect(runsTeam(admin)).toBe(false);
  });

  it('an admin who also runs a team acts on that team', () => {
    const both = person({ ...manager, is_admin: true });

    expect(mapRealMe(both, [both], { tasks: [] })).toMatchObject({ isAdmin: true, isManager: true, team: { name: 'NPI' } });
  });

  it('an inactive manager or a plain member runs nothing', () => {
    expect(runsTeam({ ...manager, active: false })).toBe(false);
    expect(runsTeam(person({ team_id: 'team1' }))).toBe(false);
  });
});
