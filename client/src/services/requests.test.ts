/* Pins the method, path, params and body each service function sends, so a wrong verb or URL (the old
   `GET /teams/{id}` 405) fails here. The mappers are replaced by pass-throughs: their output is tested in mappers.test.ts. */
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { apiClient } from './axiosInstance';
import { addMember, changeManager, createTeam, deleteTeam, getTeamMembers, getTeams, removeMember, searchUnassignedPeople } from './teams';
import { getAdmins, getAudit, searchPeople, setAdmin } from './admin';
import { addComment, createTask, deleteTask, getBoard, getTask, moveTask, updateTask } from './tasks';
import { getAllTeamsReport, getTeamReport } from './reports';
import { devSignIn, exchangeGoogleCode, getDevAccounts, getMe } from './auth';

vi.mock('./mappers', async (importOriginal) => {
  const real = await importOriginal<typeof import('./mappers')>();
  const same = (x: unknown) => x;
  return {
    ...real,
    mapTeam: same, mapPerson: same, mapAudit: same, mapTask: same, mapActivity: same, mapSummary: same, mapBoardTeam: same,
    mapTeamReport: same, mapAllTeamsReport: same, mapRealMe: same,
    mapPage: (p: { items: unknown[] }, f: (x: unknown) => unknown) => ({ ...p, items: p.items.map(f) }),
  };
});

const page = { items: [], total: 0, limit: 50, offset: 0 };
const board = { team: {}, read_only: false, tasks: [], people: [], filter_counts: {}, attention_count: 0, stats: {}, orphans: [] };
const manager = { id: 'p1', email: 'm@x.test', name: 'M', role: 'manager', is_admin: false, active: true, team_id: 't1' };

let get: MockInstance;
let post: MockInstance;
let patch: MockInstance;
let del: MockInstance;

beforeEach(() => {
  get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: [] });
  post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} });
  patch = vi.spyOn(apiClient, 'patch').mockResolvedValue({ data: {} });
  del = vi.spyOn(apiClient, 'delete').mockResolvedValue({ data: {} });
});
afterEach(() => vi.restoreAllMocks());

describe('teams service', () => {
  it('reads teams and one team\'s members with GET (there is no GET /teams/{id})', async () => {
    await getTeams();
    expect(get).toHaveBeenCalledWith('/teams');
    await getTeamMembers('t1');
    expect(get).toHaveBeenLastCalledWith('/teams/t1/members');
  });

  it('creates a team with POST /teams and snake_case keys', async () => {
    await createTeam({ name: 'NPI', initialManagerPersonId: 'p1', reason: 'new team' });
    expect(post).toHaveBeenCalledWith('/teams', { name: 'NPI', initial_manager_person_id: 'p1', reason: 'new team' });
  });

  it('deletes a team with DELETE and the confirmation in the body', async () => {
    await deleteTeam({ teamId: 't1', confirmName: 'NPI', reason: 'gone' });
    expect(del).toHaveBeenCalledWith('/teams/t1', { data: { confirm_name: 'NPI', reason: 'gone' } });
  });

  it('changes the manager with PATCH /teams/{id}/manager', async () => {
    await changeManager({ teamId: 't1', personId: 'p2', reason: 'handover' });
    expect(patch).toHaveBeenCalledWith('/teams/t1/manager', { person_id: 'p2', reason: 'handover' });
  });

  it('searches unassigned people, trimming q and dropping it when blank', async () => {
    get.mockResolvedValue({ data: page });
    await searchUnassignedPeople('  ann ');
    expect(get).toHaveBeenLastCalledWith('/people', { params: { unassigned: true, q: 'ann', limit: 50 } });
    await searchUnassignedPeople('   ');
    expect(get).toHaveBeenLastCalledWith('/people', { params: { unassigned: true, q: undefined, limit: 50 } });
  });

  it('adds a member with POST, sending no reason when it is empty', async () => {
    await addMember({ teamId: 't1', personId: 'p2', reason: 'joins' });
    expect(post).toHaveBeenLastCalledWith('/teams/t1/members', { person_id: 'p2', reason: 'joins' });
    await addMember({ teamId: 't1', personId: 'p2', reason: '' });
    expect(post).toHaveBeenLastCalledWith('/teams/t1/members', { person_id: 'p2', reason: undefined });
  });

  it('removes a member with DELETE /teams/{id}/members/{person}', async () => {
    await removeMember({ teamId: 't1', personId: 'p2', reason: 'left' });
    expect(del).toHaveBeenLastCalledWith('/teams/t1/members/p2', { data: { reason: 'left' } });
    await removeMember({ teamId: 't1', personId: 'p2', reason: '' });
    expect(del).toHaveBeenLastCalledWith('/teams/t1/members/p2', { data: { reason: undefined } });
  });
});

describe('admin service', () => {
  it('sets admin with PATCH /people/{id}/admin', async () => {
    await setAdmin({ personId: 'p1', isAdmin: true, reason: 'covers' });
    expect(patch).toHaveBeenCalledWith('/people/p1/admin', { is_admin: true, reason: 'covers' });
  });

  it('lists admins and searches people through GET /people', async () => {
    get.mockResolvedValue({ data: page });
    await getAdmins();
    expect(get).toHaveBeenLastCalledWith('/people', { params: { admins: true, limit: 200 } });
    await searchPeople(' bo ');
    expect(get).toHaveBeenLastCalledWith('/people', { params: { q: 'bo', limit: 50 } });
  });

  it('reads one audit page with limit and offset', async () => {
    get.mockResolvedValue({ data: page });
    await getAudit({ limit: 25, offset: 50 });
    expect(get).toHaveBeenCalledWith('/audit-log', { params: { limit: 25, offset: 50 } });
  });
});

describe('tasks service', () => {
  it('sends only the board filters that are set', async () => {
    get.mockResolvedValue({ data: board });
    await getBoard({ teamId: null, personId: null, attention: false, filters: [] } as never);
    expect(get).toHaveBeenLastCalledWith('/board', { params: { team: undefined, attention: undefined, person: undefined, filter: undefined } });
    await getBoard({ teamId: 't1', personId: 'p2', attention: true, filters: ['overdue', 'blocked'] } as never);
    expect(get).toHaveBeenLastCalledWith('/board', { params: { team: 't1', attention: true, person: 'p2', filter: 'overdue,blocked' } });
  });

  it('reads one task with GET /tasks/{id}', async () => {
    get.mockResolvedValue({ data: { task: {}, timeline: [] } });
    await getTask('k1');
    expect(get).toHaveBeenCalledWith('/tasks/k1');
  });

  it('creates and edits a task with snake_case fields', async () => {
    const input = { title: 'T', description: 'D', priority: 'High', dueAt: '2026-11-01', assigneeId: 'p2' } as never;
    await createTask(input);
    expect(post).toHaveBeenCalledWith('/tasks', { title: 'T', description: 'D', priority: 'High', due_at: '2026-11-01', assignee_id: 'p2' });
    await updateTask('k1', { title: 'T2' });
    expect(patch).toHaveBeenCalledWith('/tasks/k1', { title: 'T2', description: undefined, priority: undefined, due_at: undefined, assignee_id: undefined });
  });

  it('deletes with DELETE /tasks/{id}', async () => {
    await deleteTask('k1');
    expect(del).toHaveBeenCalledWith('/tasks/k1');
  });

  it('moves a task with POST /tasks/{id}/status, naming the completion day only when given', async () => {
    await moveTask('k1', 'Done' as never, 'accepted', '2026-10-18');
    expect(post).toHaveBeenLastCalledWith('/tasks/k1/status', { to: 'Done', note: 'accepted', completed_on: '2026-10-18' });
    await moveTask('k1', 'Blocked' as never, 'waiting');
    expect(post).toHaveBeenLastCalledWith('/tasks/k1/status', { to: 'Blocked', note: 'waiting', completed_on: undefined });
  });

  it('comments with POST /tasks/{id}/comments', async () => {
    await addComment('k1', 'hello');
    expect(post).toHaveBeenCalledWith('/tasks/k1/comments', { body: 'hello' });
  });
});

describe('reports service', () => {
  it('asks for the team report over From..To', async () => {
    await getTeamReport({ teamId: 't1', personId: null, attention: false, filters: [] } as never, '2026-10-01', '2026-10-31');
    expect(get).toHaveBeenCalledWith('/reports/team', { params: { team: 't1', person: undefined, from: '2026-10-01', to: '2026-10-31' } });
  });

  it('asks for the all-teams report', async () => {
    await getAllTeamsReport('2026-10-01', '2026-10-31');
    expect(get).toHaveBeenCalledWith('/reports/all-teams', { params: { from: '2026-10-01', to: '2026-10-31' } });
  });
});

describe('auth service', () => {
  it('trades the Google code with GET /auth/google/exchange', async () => {
    get.mockResolvedValue({ data: { token: 'tok', email: 'a@x.test', name: 'A' } });
    expect(await exchangeGoogleCode('abc')).toEqual({ token: 'tok', email: 'a@x.test', name: 'A' });
    expect(get).toHaveBeenCalledWith('/auth/google/exchange', { params: { code: 'abc' } });
  });

  it('lists dev accounts and explains a refused one', async () => {
    get.mockResolvedValue({ data: [{ email: 'a@x.test', name: 'A', can_sign_in: true }, { email: 'b@x.test', name: 'B', can_sign_in: false }] });
    const accounts = await getDevAccounts();
    expect(get).toHaveBeenCalledWith('/dev/accounts');
    expect(accounts[0].note).toBeUndefined();
    expect(accounts[1].note).toMatch(/refused/);
  });

  it('dev sign-in names the caller by header, lower-cased, and returns a session with no token', async () => {
    get.mockResolvedValue({ data: manager });
    expect(await devSignIn(' M@X.test ')).toEqual({ token: '', email: 'm@x.test', name: 'M' });
    expect(get).toHaveBeenCalledWith('/me', { headers: { 'X-Dev-User-Email': 'm@x.test' } });
  });

  it('getMe reads only /me for someone who runs no team', async () => {
    get.mockResolvedValue({ data: { ...manager, role: 'member', team_id: null } });
    await getMe();
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith('/me');
  });

  it('getMe also reads the team\'s members and the board for a manager', async () => {
    get.mockImplementation(async (url: string) => ({ data: url === '/me' ? manager : url === '/board' ? board : [] }));
    await getMe();
    expect(get).toHaveBeenCalledWith('/teams/t1/members');
    expect(get).toHaveBeenCalledWith('/board');
  });
});
