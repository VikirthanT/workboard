import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { KanbanBoard } from './KanbanBoard';
import type { Task } from '../../../app/types/types';

const person = { id: 'r', displayName: 'Ravi', email: 'ravi@example.test', active: true };
const task = (n: number) =>
  ({ id: `t${n}`, title: `Task ${n}`, status: 'todo', priority: 'medium', dueAt: null, assignee: person, support: null, latestReason: null, actions: { transitions: [] } }) as unknown as Task;
const totals = { todo: 12, in_progress: 0, blocked: 0, review: 0, done: 0 };

function board(sizes = {}, onSizesChange = vi.fn()) {
  const tasks = [1, 2, 3, 4, 5].map(task);
  render(<KanbanBoard tasks={tasks} columnTotals={totals} sizes={sizes} onSizesChange={onSizesChange} onOpen={vi.fn()} onTransition={vi.fn()} onBlockedDrop={vi.fn()} />);
  return onSizesChange;
}

describe('KanbanBoard', () => {
  it('counts the whole column and loads five more at a time', async () => {
    const onSizesChange = board();

    expect(screen.getByRole('region', { name: 'To Do' })).toHaveTextContent('12');
    await userEvent.click(screen.getByRole('button', { name: 'Load 5 more (7 left)' }));

    expect(onSizesChange).toHaveBeenCalledWith({ todo: 10 });
    expect(screen.queryByRole('button', { name: 'Show less' })).not.toBeInTheDocument();
  });

  it('shows less by dropping the column back to its first five', async () => {
    const onSizesChange = board({ todo: 10, done: 10 });

    await userEvent.click(screen.getAllByRole('button', { name: 'Show less' })[0]);

    expect(onSizesChange).toHaveBeenCalledWith({ done: 10 });
  });
});
