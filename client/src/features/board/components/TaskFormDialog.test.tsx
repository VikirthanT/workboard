import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TaskFormDialog } from './TaskFormDialog';
import type { Me, Task } from '../../../app/types/types';

const h = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn() }));
vi.mock('../hooks', () => ({
  useCreateTask: () => ({ mutate: h.create, isPending: false }),
  useUpdateTask: () => ({ mutate: h.update, isPending: false }),
}));

const ann = { id: 'a', displayName: 'Ann Member', email: 'ann@example.test', active: true };
const me = (assignable = [ann]) => ({ assignable }) as unknown as Me;
const open = (props: Partial<React.ComponentProps<typeof TaskFormDialog>> = {}) =>
  render(<TaskFormDialog open me={me()} onClose={vi.fn()} {...props} />);

beforeEach(() => { h.create.mockReset(); h.update.mockReset(); });

describe('TaskFormDialog', () => {
  it('keeps Add task disabled until the title is filled, and marks title as required', async () => {
    open();
    const add = screen.getByRole('button', { name: 'Add task' });
    expect(screen.getAllByText('(required)').length).toBeGreaterThan(0);
    expect(add).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Title/), '   ');
    expect(add).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Title/), 'Order parts');
    expect(add).toBeEnabled();
  });

  it('keeps Add task disabled when the team has no one to assign to', async () => {
    open({ me: me([]) });
    await userEvent.type(screen.getByLabelText(/Title/), 'Order parts');
    expect(screen.getByRole('button', { name: 'Add task' })).toBeDisabled();
  });

  it('creates the task with the trimmed title and the default assignee', async () => {
    open();
    await userEvent.type(screen.getByLabelText(/Title/), '  Order parts ');
    await userEvent.click(screen.getByRole('button', { name: 'Add task' }));
    expect(h.create).toHaveBeenCalledWith(
      { title: 'Order parts', description: '', priority: 'medium', dueAt: null, assigneeId: 'a' },
      expect.anything(),
    );
  });

  it('shows the server message when the create fails', async () => {
    h.create.mockImplementation((_i, o) => o.onError({ response: { data: { detail: { message: 'Not on your team.' } } } }));
    open();
    await userEvent.type(screen.getByLabelText(/Title/), 'Order parts');
    await userEvent.click(screen.getByRole('button', { name: 'Add task' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Not on your team.');
  });

  it('editing: the button reads Save changes and is disabled if the title is cleared', async () => {
    const task = { id: 'k1', title: 'Old', description: '', priority: 'high', dueAt: null, assignee: ann, actions: { canChangeAssignee: false } } as unknown as Task;
    open({ task });
    const save = screen.getByRole('button', { name: 'Save changes' });
    expect(save).toBeEnabled();
    expect(screen.queryByLabelText(/Assignee/)).not.toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText(/Title/));
    expect(save).toBeDisabled();
  });
});
