import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AddMemberDialog } from './AddMemberDialog';
import { RemoveMemberDialog } from './RemoveMemberDialog';
import { person } from '../../test/fixtures';

const h = vi.hoisted(() => ({ mutate: vi.fn(), toast: vi.fn(), candidates: { data: [] as unknown[], isError: false, error: null as unknown } }));
vi.mock('./hooks', () => ({
  useAddMember: () => ({ mutate: h.mutate, isPending: false }),
  useRemoveMember: () => ({ mutate: h.mutate, isPending: false }),
  useUnassignedPeople: () => h.candidates,
}));
vi.mock('../../app/components/ui/toast', () => ({ useToast: () => ({ toast: h.toast }) }));

const ann = person({ id: 'a', displayName: 'Ann Member', email: 'ann@example.test' });
const failWith = (message: string) => h.mutate.mockImplementation((_v, o) => o.onError({ response: { data: { detail: { message } } } }));

beforeEach(() => {
  vi.clearAllMocks();
  h.mutate.mockReset();
  h.candidates = { data: [ann], isError: false, error: null };
});

describe('AddMemberDialog', () => {
  const open = (props: Partial<React.ComponentProps<typeof AddMemberDialog>> = {}) =>
    render(<AddMemberDialog open teamId="t1" teamName="Alpha" onClose={vi.fn()} {...props} />);

  it('refuses to submit before a person is chosen', async () => {
    open({ reasonOptional: true }); // the picker is open on load and blocks the reason box, so skip typing one
    await userEvent.keyboard('{Escape}');
    await userEvent.click(screen.getByRole('button', { name: 'Add to team' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose a person first.');
    expect(h.mutate).not.toHaveBeenCalled();
  });

  it('adds the chosen person with the reason, toasts and closes', async () => {
    const onClose = vi.fn();
    h.mutate.mockImplementation((_v, o) => o.onSuccess());
    open({ onClose });
    await userEvent.click(await screen.findByRole('option', { name: /Ann Member/ }));
    await userEvent.type(screen.getByLabelText(/Reason/), 'joins');
    await userEvent.click(screen.getByRole('button', { name: 'Add to team' }));
    expect(h.mutate).toHaveBeenCalledWith({ personId: 'a', reason: 'joins' }, expect.anything());
    expect(h.toast).toHaveBeenCalledWith('Ann Member joined Alpha.', 'success');
    expect(onClose).toHaveBeenCalled();
  });

  it('with reasonOptional the button is enabled and an empty reason goes through', async () => {
    h.mutate.mockImplementation((_v, o) => o.onSuccess());
    open({ reasonOptional: true });
    await userEvent.click(await screen.findByRole('option', { name: /Ann Member/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Add to team' }));
    expect(h.mutate).toHaveBeenCalledWith({ personId: 'a', reason: '' }, expect.anything());
  });

  it('shows the server message when the add fails', async () => {
    failWith('Already on a team.');
    open({ reasonOptional: true });
    await userEvent.click(await screen.findByRole('option', { name: /Ann Member/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Add to team' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Already on a team.');
  });

  it('says so when no one matches, and when loading the list failed', async () => {
    h.candidates = { data: [], isError: false, error: null };
    const { unmount } = open();
    expect(await screen.findByText('No one matches.')).toBeInTheDocument();
    unmount();
    h.candidates = { data: undefined as never, isError: true, error: { message: 'Network Error' } };
    open();
    expect(await screen.findByText('Network Error')).toBeInTheDocument();
  });
});

describe('RemoveMemberDialog', () => {
  const open = (reasonOptional: boolean, onClose = vi.fn()) =>
    render(<RemoveMemberDialog team={{ id: 't1', name: 'Alpha' }} person={ann} reasonOptional={reasonOptional} onClose={onClose} />);

  it('names the person and team, and a manager may remove without a reason', async () => {
    const onClose = vi.fn();
    h.mutate.mockImplementation((_v, o) => o.onSuccess());
    open(true, onClose);
    expect(screen.getByText('Remove Ann Member from Alpha?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Remove from team' }));
    expect(h.mutate).toHaveBeenCalledWith({ personId: 'a', reason: '' }, expect.anything());
    expect(h.toast).toHaveBeenCalledWith('Ann Member removed.', 'success');
    expect(onClose).toHaveBeenCalled();
  });

  it.each([
    [0, 'Ann Member has no open tasks.'],
    [1, 'Ann Member has 1 open task, which will stay on the board and show as needing a new owner.'],
    [3, 'Ann Member has 3 open tasks, which will stay on the board and show as needing a new owner.'],
    [null, 'Their open tasks stay on the board and show as needing a new owner.'],
  ])('warns with the open-task count (%s)', (count, text) => {
    render(<RemoveMemberDialog team={{ id: 't1', name: 'Alpha' }} person={{ ...ann, openTaskCount: count }} reasonOptional onClose={vi.fn()} />);
    expect(screen.getByText(new RegExp(text.replace(/[.,]/g, '\\$&')))).toBeInTheDocument();
  });

  it('an admin must give a reason first', async () => {
    open(false);
    const submit = screen.getByRole('button', { name: 'Remove from team' });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Reason/), 'left');
    await userEvent.click(submit);
    expect(h.mutate).toHaveBeenCalledWith({ personId: 'a', reason: 'left' }, expect.anything());
  });

  it('shows the server message and stays open on failure', async () => {
    const onClose = vi.fn();
    failWith('Cannot remove the manager.');
    open(true, onClose);
    await userEvent.click(screen.getByRole('button', { name: 'Remove from team' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot remove the manager.');
    expect(onClose).not.toHaveBeenCalled();
  });
});
