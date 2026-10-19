import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TaskDetailSheet } from './TaskDetailSheet';
import type { ActivityItem, Me, Task, Transition } from '../../../app/types/types';

const h = vi.hoisted(() => ({ detail: {} as Record<string, unknown>, comment: vi.fn() }));
vi.mock('../hooks', () => ({
  useTask: () => h.detail,
  useAddComment: () => ({ mutate: h.comment, isPending: false }),
  useDeleteTask: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateTask: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock('../../../app/components/ui/toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));

const ann = { id: 'a', displayName: 'Ann Member', email: 'ann@example.test', active: true };
const actions = { canEdit: false, canDelete: false, canChangeAssignee: false, canComment: true, transitions: [] as unknown[] };
const task = (over: Omit<Partial<Task>, 'actions'> & { actions?: Partial<typeof actions> } = {}) =>
  ({
    id: 'k1', title: 'Order parts', description: '', status: 'in_progress', priority: 'high', dueAt: null,
    creator: ann, assignee: ann, returnedCount: 0, overdue: false, dueSoon: false, needsReassignment: false, returned: false, latestReason: null,
    ...over, actions: { ...actions, ...over.actions },
  }) as unknown as Task;
const comment: ActivityItem = { id: 'c1', kind: 'comment', actor: ann, note: 'On it', source: 'workboard', createdAt: '2026-10-18T09:30:00Z' } as unknown as ActivityItem;
const show = (t: Task, props: Partial<React.ComponentProps<typeof TaskDetailSheet>> = {}, timeline: ActivityItem[] = []) => {
  h.detail = { data: { task: t, timeline }, isError: false };
  const handlers = { onClose: vi.fn(), onEdit: vi.fn(), onTransition: vi.fn() };
  render(<TaskDetailSheet taskId="k1" me={{ assignable: [ann] } as unknown as Me} {...handlers} {...props} />);
  return handlers;
};

beforeEach(() => h.comment.mockReset());

describe('TaskDetailSheet', () => {
  it('says "Task not found" on an error and "Loading…" while loading', () => {
    h.detail = { data: undefined, isError: true };
    const { unmount } = render(<TaskDetailSheet taskId="k1" me={{} as Me} onClose={vi.fn()} onEdit={vi.fn()} onTransition={vi.fn()} />);
    expect(screen.getByText('Task not found')).toBeInTheDocument();
    unmount();
    h.detail = { data: undefined, isError: false };
    render(<TaskDetailSheet taskId="k1" me={{} as Me} onClose={vi.fn()} onEdit={vi.fn()} onTransition={vi.fn()} />);
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('shows Resume on a blocked task and calls onTransition with it', async () => {
    const resume = { to: 'in_progress', kind: 'resume', label: 'Resume' } as unknown as Transition;
    const t = task({ status: 'blocked', actions: { transitions: [resume] } });
    const { onTransition } = show(t);
    await userEvent.click(screen.getByRole('button', { name: 'Resume' }));
    expect(onTransition).toHaveBeenCalledWith(t, resume);
  });

  it('shows no status button for other transitions (cards move by dragging)', () => {
    show(task({ actions: { transitions: [{ to: 'review', kind: 'forward', label: 'Send to review' }] } }));
    expect(screen.queryByRole('button', { name: 'Send to review' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resume' })).not.toBeInTheDocument();
  });

  it('on a Done task shows the note, no Edit, and "Comments are closed"', () => {
    show(task({ status: 'done', actions: { canEdit: false, canComment: false } }));
    expect(screen.getByText('Note: Completed tasks cannot be edited.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Edit/ })).not.toBeInTheDocument();
    expect(screen.getByText('Comments are closed on Done tasks.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Add a comment')).not.toBeInTheDocument();
  });

  it('shows Edit, Delete and Reassign only when the API allows them', async () => {
    const t = task({ actions: { canEdit: true, canDelete: true, canChangeAssignee: true } });
    const { onEdit } = show(t);
    expect(screen.getByRole('button', { name: /Delete/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reassign/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Edit/ }));
    expect(onEdit).toHaveBeenCalledWith(t);
  });

  it('read-only (an admin on another team\'s board): no footer actions, but the comment box is there and posts', async () => {
    show(task({ actions: { canEdit: true, canComment: true } }), { readOnly: true }, [comment]);
    expect(screen.queryByRole('button', { name: /Edit/ })).not.toBeInTheDocument();
    expect(screen.getByText('On it')).toBeInTheDocument();
    const send = screen.getByRole('button', { name: 'Comment' });
    expect(send).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Add a comment'), ' looks good ');
    await userEvent.click(send);
    expect(h.comment).toHaveBeenCalledWith({ id: 'k1', body: 'looks good' }, expect.anything());
  });

  it('shows no comment box when the user cannot comment on a task that is not Done', () => {
    show(task({ actions: { canComment: false } }));
    expect(screen.queryByLabelText('Add a comment')).not.toBeInTheDocument();
    expect(screen.queryByText('Comments are closed on Done tasks.')).not.toBeInTheDocument();
  });
});
