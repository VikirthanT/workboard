import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TeamsView } from './TeamsView';
import { AdminsPanel } from './AdminsPanel';
import { AuditLog } from './AuditLog';
import { person, team } from '../../test/fixtures';
import type { AuditEntry } from '../../app/types/types';

const h = vi.hoisted(() => ({
  me: undefined as unknown,
  teams: {} as Record<string, unknown>,
  members: [] as unknown[],
  admins: {} as Record<string, unknown>,
  audit: {} as Record<string, unknown>,
  auditPages: [] as number[],
  auditThrows: false,
}));
vi.mock('../../hooks', () => ({ useCurrentUser: () => ({ data: h.me }) }));
vi.mock('./hooks', () => ({
  useTeams: () => h.teams,
  useAllTeamMembers: () => h.members,
  useAdmins: () => h.admins,
  useAudit: (page: number) => { if (h.auditThrows) throw new Error('boom'); h.auditPages.push(page); return h.audit; },
}));
// The dialogs have their own tests; here they only need to show that they opened.
vi.mock('./CreateTeamDialog', () => ({ CreateTeamDialog: ({ open }: { open: boolean }) => open && <div>create-team-open</div> }));
vi.mock('./DeleteTeamDialog', () => ({ DeleteTeamDialog: ({ team }: { team: { name: string } | null }) => team && <div>delete-open {team.name}</div> }));
vi.mock('./AddAdminDialog', () => ({ AddAdminDialog: ({ open }: { open: boolean }) => open && <div>add-admin-open</div> }));
vi.mock('./PersonDialogs', () => ({
  ManagerChangeDialog: () => null,
  AdminToggleDialog: ({ person }: { person: { displayName: string } }) => <div>revoke-open {person.displayName}</div>,
}));
vi.mock('../team/AddMemberDialog', () => ({ AddMemberDialog: () => null }));
vi.mock('../team/RemoveMemberDialog', () => ({ RemoveMemberDialog: () => null }));

const admin = { user: { id: 'u1' }, isAdmin: true };
const loaded = (data: unknown) => ({ data, isError: false, error: null });
const alpha = team({ id: 't1', name: 'Alpha' });
const beta = team({ id: 't2', name: 'Beta' });
const ann = person({ id: 'a', displayName: 'Ann Member' });
const bo = person({ id: 'b', displayName: 'Bo Member', teamId: 't2' });

beforeEach(() => {
  h.me = admin;
  h.teams = loaded([alpha, beta]);
  h.members = [loaded([ann]), loaded([bo])];
  h.admins = loaded([]);
  h.audit = loaded({ items: [], total: 0, offset: 0, limit: 50 });
  h.auditPages = [];
  h.auditThrows = false;
});

describe('TeamsView', () => {
  it('shows "Admins only" to a non-admin', () => {
    h.me = { user: { id: 'u2' }, isAdmin: false };
    render(<TeamsView />);
    expect(screen.getByText('Admins only')).toBeInTheDocument();
    expect(screen.queryByText('Create team')).not.toBeInTheDocument();
  });

  it('lists every team with its people and a count line', () => {
    render(<TeamsView />);
    expect(screen.getByText('2 teams, 2 people')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Alpha' })).toBeInTheDocument();
    expect(screen.getByText('Bo Member')).toBeInTheDocument();
  });

  it('shows the empty state, whose button opens Create team', async () => {
    h.teams = loaded([]);
    h.members = [];
    render(<TeamsView />);
    expect(screen.getByText('No teams yet')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: /Create team/ })[1]);
    expect(screen.getByText('create-team-open')).toBeInTheDocument();
  });

  it('shows the error when the teams fail to load', () => {
    h.teams = { data: undefined, isError: true, error: { message: 'Boom' } };
    h.members = [];
    render(<TeamsView />);
    expect(screen.getByText('Could not load teams')).toBeInTheDocument();
    expect(screen.getByText('Boom')).toBeInTheDocument();
  });

  it('shows the error when one team\'s people fail to load', () => {
    h.members = [loaded([ann]), { data: undefined, isError: true, error: { message: 'No access' } }];
    render(<TeamsView />);
    expect(screen.getByText('Could not load a team’s people')).toBeInTheDocument();
  });

  it('filters by search, hides teams with no match, and says so when nobody matches', async () => {
    render(<TeamsView />);
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search people' }), 'bo');
    expect(screen.queryByRole('region', { name: 'Alpha' })).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Beta' })).toBeInTheDocument();
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search people' }), 'zzz');
    expect(screen.getByText('No one matches that search.')).toBeInTheDocument();
  });

  it('a render error in the Audit log tab shows its fallback; the heading and the other tabs still work', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    h.auditThrows = true;
    h.admins = loaded([person({ id: 'u1', displayName: 'Only Admin', isAdmin: true })]);
    render(<TeamsView />);
    await userEvent.click(screen.getByRole('tab', { name: 'Audit log' }));
    expect(screen.getByText('The audit log could not be shown. Reloading usually fixes it.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Teams' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: 'Admins' }));
    expect(screen.getByText('Only Admin (You)')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: 'Teams' }));
    expect(screen.getByRole('region', { name: 'Alpha' })).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it('opens Delete team for the chosen team', async () => {
    render(<TeamsView />);
    await userEvent.click(screen.getByRole('button', { name: 'Delete team Beta' }));
    expect(screen.getByText('delete-open Beta')).toBeInTheDocument();
  });
});

describe('AdminsPanel', () => {
  it('locks the dustbin when there is one admin', () => {
    h.admins = loaded([person({ id: 'u1', displayName: 'Only Admin', isAdmin: true, teamName: null })]);
    render(<AdminsPanel currentUserId="u1" />);
    expect(screen.getByText('Only Admin (You)')).toBeInTheDocument();
    expect(screen.getByText('No team')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Only Admin is the only admin' })).toBeDisabled();
  });

  it('with two admins the dustbin opens the revoke dialog', async () => {
    h.admins = loaded([person({ id: 'u1', displayName: 'One', isAdmin: true }), person({ id: 'u2', displayName: 'Two', isAdmin: true, role: 'manager' })]);
    render(<AdminsPanel currentUserId="u1" />);
    expect(screen.getByText('Manager, Alpha')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Remove admin access from Two' }));
    expect(screen.getByText('revoke-open Two')).toBeInTheDocument();
  });

  it('Add admin opens its dialog', async () => {
    h.admins = loaded([person({ id: 'u1', isAdmin: true })]);
    render(<AdminsPanel currentUserId="u1" />);
    await userEvent.click(screen.getByRole('button', { name: /Add admin/ }));
    expect(screen.getByText('add-admin-open')).toBeInTheDocument();
  });

  it('shows the error when the admins fail to load', () => {
    h.admins = { data: undefined, isError: true, error: { message: 'Nope' } };
    render(<AdminsPanel currentUserId="u1" />);
    expect(screen.getByText('Could not load the admins')).toBeInTheDocument();
  });
});

describe('AuditLog', () => {
  const entry = (over: Partial<AuditEntry>): AuditEntry => ({
    id: 'e1', action: 'admin.grant', actorName: 'Ann Member', personName: 'Bo Member', teamName: null, reason: 'covers', details: null, createdAt: '2026-10-18T09:30:00Z', ...over,
  });
  const pageOf = (items: AuditEntry[], total: number, offset = 0) => loaded({ items, total, offset, limit: 50 });

  it('shows rows with who, the sentence and the reason, "System" for no actor, and a placeholder for no reason', () => {
    h.audit = pageOf([entry({}), entry({ id: 'e2', actorName: null, reason: null, action: 'member.add', teamName: 'Alpha' })], 2);
    render(<AuditLog />);
    expect(screen.getByText('Made Bo Member an admin')).toBeInTheDocument();
    expect(screen.getByText('covers')).toBeInTheDocument();
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('No reason given')).toBeInTheDocument();
  });

  it('says "No changes yet." for an empty log, with both buttons disabled', () => {
    render(<AuditLog />);
    expect(screen.getByText('No changes yet.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Newer/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Older/ })).toBeDisabled();
  });

  it('Older is enabled on the first of two pages and moves to page 1; Newer is disabled on page 0', async () => {
    h.audit = pageOf([entry({})], 80);
    render(<AuditLog />);
    expect(screen.getByRole('button', { name: /Newer/ })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: /Older/ }));
    expect(h.auditPages.at(-1)).toBe(1);
    expect(screen.getByRole('button', { name: /Newer/ })).toBeEnabled();
  });

  it('Older is disabled on the last page', () => {
    h.audit = pageOf([entry({})], 51, 50);
    render(<AuditLog />);
    expect(screen.getByRole('button', { name: /Older/ })).toBeDisabled();
  });

  it('shows the error when the log fails to load', () => {
    h.audit = { data: undefined, isError: true, error: { message: 'Forbidden' } };
    render(<AuditLog />);
    expect(screen.getByText('Could not load the audit log')).toBeInTheDocument();
    expect(screen.getByText('Forbidden')).toBeInTheDocument();
  });
});
