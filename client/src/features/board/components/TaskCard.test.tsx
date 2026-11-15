import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TaskCard } from './TaskCard';
import type { Task } from '../../../app/types/types';

const person = (displayName: string) => ({ id: displayName, displayName, email: `${displayName}@example.test`, active: true });
const task = (over: Partial<Task> = {}) =>
  ({ id: 't', title: 'Wire harness', status: 'todo', priority: 'medium', dueAt: null, assignee: person('Ravi'), support: null, latestReason: null, ...over }) as unknown as Task;

describe('TaskCard', () => {
  it('shows the task number before the title', () => {
    render(<TaskCard task={task({ number: 33 })} />);
    expect(screen.getByText('#33')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Task 33, Wire harness/ })).toBeInTheDocument();
  });

  it('shows who is giving support, only when someone is', () => {
    const { rerender } = render(<TaskCard task={task()} />);
    expect(screen.queryByText(/Support:/)).not.toBeInTheDocument();

    rerender(<TaskCard task={task({ support: person('Divya') })} />);
    expect(screen.getByText(/Support:/)).toHaveTextContent('Support: Divya');
  });
});
