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
  channels: [] as { id: string; name: string }[],
  syncPeople: { mutate: vi.fn(), isPending: false },
  toast: vi.fn(),
}));
vi.mock('../../hooks', () => ({ useCurrentUser: () => ({ data: h.me }) }));
vi.mock('./hooks', () => ({
  useTeams: () => h.teams,
  useAllTeamMembers: () => h.members,
  useAdmins: () => h.admins,
  useStandupChannels: () => ({ data: h.channels }),
  useSyncPeople: () => h.syncPeople,
  useAudit: (page: number) => { if (h.auditThrows) throw new Error('boom'); h.auditPages.push(page); return h.audit; },
}));
// The dialogs have their own tests; here they only need to show that they opened.
vi.mock('./CreateTeamDialog', () => ({ CreateTeamDialog: ({ open }: { open: boolean }) => open && <div>create-team-open</div> }));
vi.mock('./DeleteTeamDialog', () => ({ DeleteTeamDialog: ({ team }: { team: { name: string } | null }) => team && <div>delete-open {team.name}</div> }));
vi.mock('./EditStandupChannelDialog', () => ({ EditStandupChannelDialog: ({ team }: { team: { name: string } | null }) => team && <div>channel-open {team.name}</div> }));
vi.mock('./AddAdminDialog', () => ({ AddAdminDialog: ({ open }: { open: boolean }) => open && <div>add-admin-open</div> }));
vi.mock('./PersonDialogs', () => ({
  ManagerChangeDialog: () => null,
  AdminToggleDialog: ({ person }: { person: { displayName: string } }) => <div>revoke-open {person.displayName}</div>,
}));
vi.mock('../team/AddMemberDialog', () => ({ AddMemberDialog: () => null }));
vi.mock('../team/PullFromSlackDialog', () => ({ PullFromSlackDialog: ({ team }: { team: { name: string } | null }) => team && <div>pull-open {team.name}</div> }));
vi.mock('../../app/components/ui/toast', () => ({ useToast: () => ({ toast: h.toast }) }));
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
  h.channels = [];
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

  it('shows each team\'s standup channel by name, falls back to the id, and says when there is none', () => {
    h.teams = loaded([team({ id: 't1', name: 'Alpha', standupChannelId: 'C0A' }), team({ id: 't2', name: 'Beta', standupChannelId: 'C0GONE' }), team({ id: 't3', name: 'Gamma' })]);
    h.members = [loaded([]), loaded([]), loaded([])];
    h.channels = [{ id: 'C0A', name: 'standup-alpha' }];
    render(<TeamsView />);
    expect(screen.getByRole('button', { name: 'Standup channel of Alpha' })).toHaveTextContent('standup-alpha');
    expect(screen.getByRole('button', { name: 'Standup channel of Beta' })).toHaveTextContent('C0GONE');
    expect(screen.getByRole('button', { name: 'Standup channel of Gamma' })).toHaveTextContent('No standup channel');
  });

  it('opens the standup channel dialog for the chosen team', async () => {
    render(<TeamsView />);
    await userEvent.click(screen.getByRole('button', { name: 'Standup channel of Beta' }));
    expect(screen.getByText('channel-open Beta')).toBeInTheDocument();
  });

  it('pulls people from Slack for any team, but only once the team has a standup channel', async () => {
    h.teams = loaded([team({ id: 't1', name: 'Alpha', standupChannelId: 'C0A' }), team({ id: 't2', name: 'Beta' })]);
    h.members = [loaded([]), loaded([])];
    render(<TeamsView />);

    const [alphaButton, betaButton] = screen.getAllByRole('button', { name: /Pull from Slack/ });
    expect(betaButton).toBeDisabled(); // no channel set: nothing to read
    expect(alphaButton).toBeEnabled();
    await userEvent.click(alphaButton);
    expect(screen.getByText('pull-open Alpha')).toBeInTheDocument();
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

  describe('Sync people from Slack', () => {
    beforeEach(() => { h.syncPeople = { mutate: vi.fn(), isPending: false }; h.toast.mockReset(); });

    it('is locked from the first press until the sync ends, and says so on the button', async () => {
      const { rerender } = render(<TeamsView />);
      const button = screen.getByRole('button', { name: 'Sync people from Slack' });

      await userEvent.dblClick(button); // two presses before the first has finished
      expect(h.syncPeople.mutate).toHaveBeenCalledTimes(1);

      h.syncPeople.isPending = true;
      rerender(<TeamsView />);
      expect(screen.getByRole('button', { name: 'Syncing people…' })).toBeDisabled();

      h.syncPeople.isPending = false;
      h.syncPeople.mutate.mock.calls[0][1].onSettled(); // the sync ends
      rerender(<TeamsView />);
      await userEvent.click(screen.getByRole('button', { name: 'Sync people from Slack' }));
      expect(h.syncPeople.mutate).toHaveBeenCalledTimes(2);
    });

    it('says what the run did, and which of the deactivated were on a team', async () => {
      h.syncPeople.mutate.mockImplementation((_v, o) => { o.onSuccess({ people: 120, added: 3, reactivated: 1, deactivated: 2, deactivatedOnATeam: 1, newAdmins: 0, skipped: 0 }); o.onSettled(); });
      render(<TeamsView />);

      await userEvent.click(screen.getByRole('button', { name: 'Sync people from Slack' }));

      const [message, tone] = h.toast.mock.calls[0];
      expect(tone).toBe('success');
      expect(message).toContain('120 people in Slack, 3 added, 1 back, 2 deactivated');
      expect(message).toContain('1 of the deactivated were on a team: their open tasks need a new owner');
    });

    it('shows the server\'s own words when it cannot sync (Slack not set up, too many removals)', async () => {
      h.syncPeople.mutate.mockImplementation((_v, o) => { o.onError({ response: { data: { detail: { message: 'Slack is not set up on this server, so the people cannot be read from it.' } } } }); o.onSettled(); });
      render(<TeamsView />);

      await userEvent.click(screen.getByRole('button', { name: 'Sync people from Slack' }));

      expect(h.toast).toHaveBeenCalledWith('Slack is not set up on this server, so the people cannot be read from it.', 'warning');
    });
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
