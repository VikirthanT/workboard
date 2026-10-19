import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CreateTeamDialog } from './CreateTeamDialog';
import { DeleteTeamDialog } from './DeleteTeamDialog';
import { AdminToggleDialog, ManagerChangeDialog } from './PersonDialogs';
import { AddAdminDialog } from './AddAdminDialog';
import { person, team } from '../../test/fixtures';

const h = vi.hoisted(() => ({ mutate: vi.fn(), toast: vi.fn(), unassigned: { data: [] as unknown[] }, admins: { data: [] as unknown[] } }));
vi.mock('./hooks', () => ({
  useCreateTeam: () => ({ mutate: h.mutate, isPending: false }),
  useDeleteTeam: () => ({ mutate: h.mutate, isPending: false }),
  useChangeManager: () => ({ mutate: h.mutate, isPending: false }),
  useSetAdmin: () => ({ mutate: h.mutate, isPending: false }),
  useAdminCandidates: () => h.admins,
}));
vi.mock('../team/hooks', async (orig) => ({ ...(await orig<object>()), useUnassignedPeople: () => h.unassigned }));
vi.mock('../../app/components/ui/toast', () => ({ useToast: () => ({ toast: h.toast }) }));

const ann = person({ id: 'a', displayName: 'Ann Member', email: 'ann@example.test' });
const bob = person({ id: 'b', displayName: 'Bob Admin', email: 'bob@example.test', isAdmin: true });
const succeed = (arg?: unknown) => h.mutate.mockImplementation((_v, o) => o.onSuccess(arg));
const failWith = (message: string) => h.mutate.mockImplementation((_v, o) => o.onError({ response: { data: { detail: { message } } } }));
const reason = (text = 'because') => userEvent.type(screen.getByLabelText(/Reason/), text);
const alert = () => screen.findByRole('alert');

beforeEach(() => {
  h.mutate.mockReset();
  h.toast.mockReset();
  h.unassigned = { data: [ann] };
  h.admins = { data: [ann, bob] };
});

describe('CreateTeamDialog', () => {
  const open = (onClose = vi.fn()) => render(<CreateTeamDialog open onClose={onClose} />);
  const pickManager = async () => {
    await userEvent.click(screen.getByRole('combobox', { name: /Manager/ }));
    await userEvent.click(await screen.findByRole('option', { name: /Ann Member/ }));
  };

  it('needs a name', async () => {
    open();
    await reason();
    await userEvent.click(screen.getByRole('button', { name: 'Create team' }));
    expect(await alert()).toHaveTextContent('Give the team a name.');
    expect(h.mutate).not.toHaveBeenCalled();
  });

  it('needs a first person', async () => {
    open();
    await userEvent.type(screen.getByLabelText('Team name'), 'Beta');
    await reason();
    await userEvent.click(screen.getByRole('button', { name: 'Create team' }));
    expect(await alert()).toHaveTextContent(/Choose the team.s first person/);
    expect(h.mutate).not.toHaveBeenCalled();
  });

  it('creates the team with the trimmed name, the chosen manager and the reason', async () => {
    const onClose = vi.fn();
    succeed({ name: 'Beta' });
    open(onClose);
    await userEvent.type(screen.getByLabelText('Team name'), '  Beta ');
    await pickManager();
    await reason('new team');
    await userEvent.click(screen.getByRole('button', { name: 'Create team' }));
    expect(h.mutate).toHaveBeenCalledWith({ name: 'Beta', initialManagerPersonId: 'a', reason: 'new team' }, expect.anything());
    expect(h.toast).toHaveBeenCalledWith('Beta created.', 'success');
    expect(onClose).toHaveBeenCalled();
  });

  it('shows the server message (duplicate name)', async () => {
    failWith('A team with that name exists.');
    open();
    await userEvent.type(screen.getByLabelText('Team name'), 'Beta');
    await pickManager();
    await reason();
    await userEvent.click(screen.getByRole('button', { name: 'Create team' }));
    expect(await alert()).toHaveTextContent('A team with that name exists.');
  });
});

describe('DeleteTeamDialog', () => {
  const alpha = team({ id: 't1', name: 'Alpha' });

  it('renders nothing without a team', () => {
    render(<DeleteTeamDialog team={null} onClose={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('refuses when the typed name does not match', async () => {
    render(<DeleteTeamDialog team={alpha} onClose={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/to confirm/), 'Alph');
    await reason();
    await userEvent.click(screen.getByRole('button', { name: 'Delete team' }));
    expect(await alert()).toHaveTextContent(/Type the team.s name to confirm/);
    expect(h.mutate).not.toHaveBeenCalled();
  });

  it('deletes when the name matches, ignoring case and spaces', async () => {
    const onClose = vi.fn();
    succeed();
    render(<DeleteTeamDialog team={alpha} onClose={onClose} />);
    await userEvent.type(screen.getByLabelText(/to confirm/), ' alpha ');
    await reason('closed');
    await userEvent.click(screen.getByRole('button', { name: 'Delete team' }));
    expect(h.mutate).toHaveBeenCalledWith({ teamId: 't1', confirmName: 'alpha', reason: 'closed' }, expect.anything());
    expect(h.toast).toHaveBeenCalledWith('Alpha deleted.', 'success');
    expect(onClose).toHaveBeenCalled();
  });
});

describe('PersonDialogs', () => {
  it('ManagerChangeDialog changes the manager with the reason', async () => {
    succeed();
    render(<ManagerChangeDialog team={{ id: 't1', name: 'Alpha' }} person={ann} onClose={vi.fn()} />);
    await reason('handover');
    await userEvent.click(screen.getByRole('button', { name: 'Make manager' }));
    expect(h.mutate).toHaveBeenCalledWith({ teamId: 't1', personId: 'a', reason: 'handover' }, expect.anything());
  });

  it('AdminToggleDialog grants admin', async () => {
    succeed();
    render(<AdminToggleDialog person={ann} isAdmin onClose={vi.fn()} />);
    await reason();
    await userEvent.click(screen.getByRole('button', { name: 'Make admin' }));
    expect(h.mutate).toHaveBeenCalledWith({ personId: 'a', isAdmin: true, reason: 'because' }, expect.anything());
    expect(h.toast).toHaveBeenCalledWith('Ann Member is now an admin.', 'success');
  });

  it('AdminToggleDialog revokes admin, and shows the last-admin refusal', async () => {
    failWith('The last admin cannot be removed.');
    render(<AdminToggleDialog person={bob} isAdmin={false} onClose={vi.fn()} />);
    expect(screen.getByText('Revoke admin from Bob Admin?')).toBeInTheDocument();
    await reason();
    await userEvent.click(screen.getByRole('button', { name: 'Revoke admin' }));
    expect(h.mutate).toHaveBeenCalledWith({ personId: 'b', isAdmin: false, reason: 'because' }, expect.anything());
    expect(await alert()).toHaveTextContent('The last admin cannot be removed.');
  });
});

describe('AddAdminDialog', () => {
  it('does not offer people who are already admins', async () => {
    render(<AddAdminDialog open onClose={vi.fn()} />);
    expect(await screen.findByRole('option', { name: /Ann Member/ })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /Bob Admin/ })).not.toBeInTheDocument();
  });

  it('makes the chosen person an admin with the reason', async () => {
    succeed();
    render(<AddAdminDialog open onClose={vi.fn()} />);
    await userEvent.click(await screen.findByRole('option', { name: /Ann Member/ }));
    await reason('covers');
    await userEvent.click(screen.getByRole('button', { name: 'Make admin' }));
    expect(h.mutate).toHaveBeenCalledWith({ personId: 'a', isAdmin: true, reason: 'covers' }, expect.anything());
  });

  it('refuses to submit before a person is chosen', async () => {
    render(<AddAdminDialog open onClose={vi.fn()} />);
    await userEvent.keyboard('{Escape}'); // close the picker, which opens with the dialog
    await reason();
    await userEvent.click(screen.getByRole('button', { name: 'Make admin' }));
    expect(await alert()).toHaveTextContent('Choose a person first.');
    expect(h.mutate).not.toHaveBeenCalled();
  });
});
