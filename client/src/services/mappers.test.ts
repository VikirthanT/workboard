/* Contract test: JSON shaped exactly like the server's responses (server/tasks/schemas.py) goes through the mappers.
   The payloads are synthetic. If the server's shape changes, this is where the client finds out. */
import { describe, expect, it } from 'vitest';
import type { WireActivity, WireBoardTeam, WireIdentity, WireTask } from './backendTypes';
import { mapActivity, mapBoardTeam, mapChannelMembers, mapPerson, mapRealMe, mapStandupChannel, mapSuggestionsPage, mapTask, mapTeam, runsTeam } from './mappers';

const ravi = { id: 'p-ravi', name: 'Ravi', email: 'ravi@atimotors.com', active: true };
const asha = { id: 'p-asha', name: 'Asha', email: 'asha@atimotors.com', active: true };

const serverTask = (over: Partial<WireTask> = {}): WireTask => ({
  id: 't1', number: 7, team_id: 'team1', title: 'Wire harness', description: '', status: 'blocked', priority: 'high', due_at: '2026-10-30',
  creator: asha, assignee: ravi, support: null, project: null, returned_count: 0,
  created_at: '2026-10-17T08:00:00Z', updated_at: '2026-10-17T09:00:00Z', closed_at: null,
  overdue: false, due_soon: true, needs_reassignment: false, returned: false,
  latest_reason: { kind: 'blocked', note: 'waiting on supplier', at: '2026-10-17T09:00:00Z', actor_name: 'Asha' },
  actions: {
    can_edit: true, can_delete: false, can_change_assignee: true, can_comment: true,
    transitions: [{ to: 'in_progress', kind: 'resume', label: 'Resume', needs_reason: false }],
  },
  ...over,
});

describe('server team and standup channel -> client', () => {
  it('maps a team with and without a standup channel, and a channel by its Slack id', () => {
    const wire = { id: 'team1', name: 'NPI', manager: null, member_count: 3, standup_channel_id: 'C0NPI' };

    expect(mapTeam(wire).standupChannelId).toBe('C0NPI');
    expect(mapTeam({ ...wire, standup_channel_id: null }).standupChannelId).toBeNull();
    expect(mapStandupChannel({ slack_channel_id: 'C0NPI', name: 'standup-npi' })).toEqual({ id: 'C0NPI', name: 'standup-npi' });
  });
});

describe('server Slack channel members -> client', () => {
  const wirePerson = { id: 'p1', name: 'Meena', email: 'meena@example.test', slack_user_id: 'U1', role: 'member', is_admin: false, active: true, team_id: null, team_name: null };

  it('maps each person with what adding them would do, and treats an unknown state as unavailable', () => {
    const mapped = mapChannelMembers({
      channel_id: 'C0NPI',
      members: [
        { person: wirePerson, state: 'available', team_name: null },
        { person: { ...wirePerson, id: 'p2' }, state: 'on_other_team', team_name: 'QA' },
        { person: { ...wirePerson, id: 'p3' }, state: 'something_new', team_name: null },
      ],
      not_in_directory: 4,
    });

    expect(mapped.channelId).toBe('C0NPI');
    expect(mapped.notInDirectory).toBe(4);
    expect(mapped.members.map((m) => [m.person.displayName, m.state, m.teamName])).toEqual([
      ['Meena', 'available', null], ['Meena', 'on_other_team', 'QA'], ['Meena', 'unavailable', null],
    ]);
  });
});

describe('server suggestions page -> client', () => {
  const wireSuggestion = {
    id: 's1', person_id: 'p-ravi', title: 'Design weld jig', description: 'Ready.', kind: 'blocker', priority: 'high',
    start_at: '2026-11-09', due_at: null, due_is_default: false, subtasks: ['table'], evidence_quote: 'Start the weld jig design',
    related_to: 'Order samples', state: 'pending', late_reply: true, standup_date: '2026-11-09', task_id: null,
  };

  it('maps people, their standup (or none) and each suggestion to camelCase', () => {
    const page = mapSuggestionsPage({
      standup_channel_id: 'C0NPI',
      last_synced_at: '2026-11-13T09:42:00Z',
      standup_problem: 'unreadable',
      people: [
        {
          person: { id: 'p-ravi', name: 'Ravi', email: 'ravi@atimotors.com', role: 'member' },
          standup: { date: '2026-11-09', posted_at: '2026-11-11T04:09:21Z', late_reply: true, last_week: '- a', this_week: '- b', blockers: null, message: null },
          suggestions: [wireSuggestion],
        },
        { person: { id: 'p-asha', name: 'Asha', email: 'asha@atimotors.com', role: 'manager' }, standup: null, suggestions: [] },
      ],
    });

    expect(page.standupChannelId).toBe('C0NPI');
    expect(page.lastSyncedAt).toBe('2026-11-13T09:42:00Z');
    expect(page.standupProblem).toBe('unreadable');
    expect(mapSuggestionsPage({ standup_channel_id: null, last_synced_at: null, standup_problem: 'something new', people: [] }).standupProblem).toBeNull();
    expect(page.people[0].person).toEqual({ id: 'p-ravi', displayName: 'Ravi', email: 'ravi@atimotors.com', role: 'member' });
    expect(page.people[0].standup).toEqual({
      date: '2026-11-09', postedAt: '2026-11-11T04:09:21Z', lateReply: true, lastWeek: '- a', thisWeek: '- b', blockers: null, message: null,
    });
    expect(page.people[0].suggestions[0]).toEqual({
      id: 's1', personId: 'p-ravi', title: 'Design weld jig', description: 'Ready.', kind: 'blocker', priority: 'high',
      startAt: '2026-11-09', dueAt: null, dueIsDefault: false, subtasks: ['table'], evidenceQuote: 'Start the weld jig design',
      relatedTo: 'Order samples', state: 'pending', lateReply: true, standupDate: '2026-11-09', taskId: null,
    });
    expect(page.people[1].person.role).toBe('manager');
    expect(page.people[1].standup).toBeNull();
  });
});

describe('server task -> client task', () => {
  it('maps people by their `name`, the reason, and the actions the server allows', () => {
    const task = mapTask(serverTask());

    expect(task.number).toBe(7);
    expect(task.assignee.displayName).toBe('Ravi');
    expect(task.creator.displayName).toBe('Asha');
    expect(task.latestReason).toEqual({ kind: 'blocked', note: 'waiting on supplier', at: '2026-10-17T09:00:00Z', actorName: 'Asha' });
    expect(task.actions.transitions).toEqual([{ to: 'in_progress', kind: 'resume', label: 'Resume', needsReason: false }]);
    expect(task.dueSoon).toBe(true);
  });

  it('maps the optional support person and project, and keeps them null when not set', () => {
    expect(mapTask(serverTask())).toMatchObject({ support: null, project: null });

    const task = mapTask(serverTask({ support: asha, project: 'P1' }));

    expect(task.support?.displayName).toBe('Asha');
    expect(task.project).toBe('P1');
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

  it('the open-task count comes through when the server sends it, and is null when it does not', () => {
    expect(mapPerson(person({ open_task_count: 3 })).openTaskCount).toBe(3);
    expect(mapPerson(person({ open_task_count: 0 })).openTaskCount).toBe(0);
    expect(mapPerson(person({})).openTaskCount).toBeNull();
    expect(mapPerson(person({ open_task_count: null })).openTaskCount).toBeNull();
  });

  it('an inactive manager or a plain member runs nothing', () => {
    expect(runsTeam({ ...manager, active: false })).toBe(false);
    expect(runsTeam(person({ team_id: 'team1' }))).toBe(false);
  });
});
