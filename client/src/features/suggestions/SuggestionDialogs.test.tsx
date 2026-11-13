import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Suggestion } from '../../app/types/types';
import { AddSuggestionsDialog } from './AddSuggestionsDialog';
import { EditSuggestionDialog } from './EditSuggestionDialog';

const h = vi.hoisted(() => ({ mutate: vi.fn() }));
vi.mock('./hooks', () => ({
  useAddSuggestions: () => ({ mutate: h.mutate, isPending: false }),
  useEditSuggestion: () => ({ mutate: h.mutate, isPending: false }),
}));

const suggestion = (over: Partial<Suggestion>): Suggestion => ({
  id: 's1', personId: 'p-ravi', title: 'Design weld jig', description: 'The jig design is ready.', kind: 'new', priority: 'medium',
  startAt: '2026-11-09', dueAt: '2026-11-13', dueIsDefault: true, subtasks: [], evidenceQuote: 'Start the weld jig design', relatedTo: null,
  state: 'pending', lateReply: false, standupDate: '2026-11-09', taskId: null, ...over,
});
const ravi = { id: 'p-ravi', displayName: 'Ravi', email: 'ravi@example.test', role: 'member' as const };
const asha = { id: 'p-asha', displayName: 'Asha', email: 'asha@example.test', role: 'manager' as const };

beforeEach(() => { h.mutate.mockReset(); }); // braces: a returned function would be run as a cleanup, with no arguments

describe('AddSuggestionsDialog', () => {
  const groups = [
    { person: ravi, suggestions: [suggestion({ id: 's1' }), suggestion({ id: 's2', title: 'Order bracket samples', description: 'Samples are ordered.', priority: 'high' })] },
    { person: asha, suggestions: [suggestion({ id: 's3', title: 'Review test plan', description: 'The plan is reviewed.', personId: 'p-asha' })] },
  ];
  const open = (onClose = vi.fn(), onAdded = vi.fn()) => render(<AddSuggestionsDialog teamId="t1" groups={groups} onClose={onClose} onAdded={onAdded} />);

  it('starts with everything ticked and says what Create will do', () => {
    open();
    expect(screen.getByText('Add 3 tasks')).toBeInTheDocument();
    expect(screen.getByText(/3 tasks for 2 people/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create (3)' })).toBeEnabled();
    expect(screen.getByText('The jig design is ready.')).toBeInTheDocument();
  });

  it('unticking drops a task from the count and from what is created', async () => {
    const onClose = vi.fn(), onAdded = vi.fn();
    h.mutate.mockImplementation((_ids, o) => o.onSuccess());
    open(onClose, onAdded);
    await userEvent.click(screen.getByRole('checkbox', { name: /Order bracket samples/ }));
    expect(screen.getByText('Add 2 tasks')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Create (2)' }));
    expect(h.mutate).toHaveBeenCalledWith(['s1', 's3'], expect.anything());
    expect(onAdded).toHaveBeenCalledWith(2);
    expect(onClose).toHaveBeenCalled();
  });

  it('cannot create when nothing is ticked', async () => {
    open();
    for (const box of screen.getAllByRole('checkbox')) await userEvent.click(box);
    expect(screen.getByText('Nothing is ticked, so nothing will be created.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create (0)' })).toBeDisabled();
  });

  it('shows the server message, which names the suggestion that broke a rule', async () => {
    h.mutate.mockImplementation((_ids, o) => o.onError({ response: { data: { detail: { message: '“Design weld jig”: The due date cannot be in the past.' } } } }));
    const onClose = vi.fn();
    open(onClose);
    await userEvent.click(screen.getByRole('button', { name: 'Create (3)' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('“Design weld jig”: The due date cannot be in the past.');
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('EditSuggestionDialog', () => {
  const assignees = [{ id: 'p-ravi', displayName: 'Ravi' }, { id: 'p-asha', displayName: 'Asha' }];
  const open = (onClose = vi.fn(), onSaved = vi.fn()) => render(<EditSuggestionDialog suggestion={suggestion({})} assignees={assignees} onClose={onClose} onSaved={onSaved} />);

  it('renders nothing without a suggestion', () => {
    render(<EditSuggestionDialog suggestion={null} assignees={assignees} onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('saving without a change selects it without calling the server, so the default due date stays the default', async () => {
    const onClose = vi.fn(), onSaved = vi.fn();
    open(onClose, onSaved);
    await userEvent.click(screen.getByRole('button', { name: 'Save and select' }));
    expect(h.mutate).not.toHaveBeenCalled();
    expect(onSaved).toHaveBeenCalledWith('s1');
    expect(onClose).toHaveBeenCalled();
  });

  it('sends only the fields that changed', async () => {
    h.mutate.mockImplementation((_v, o) => o.onSuccess());
    const onSaved = vi.fn();
    open(vi.fn(), onSaved);
    const title = screen.getByLabelText(/Title/);
    await userEvent.clear(title);
    await userEvent.type(title, '  Build the weld jig ');
    await userEvent.click(screen.getByRole('button', { name: 'Save and select' }));
    expect(h.mutate).toHaveBeenCalledWith({ id: 's1', patch: { title: 'Build the weld jig' } }, expect.anything());
    expect(onSaved).toHaveBeenCalledWith('s1');
  });

  it('needs a title and a description', async () => {
    open();
    await userEvent.clear(screen.getByLabelText(/Description/));
    expect(screen.getByRole('button', { name: 'Save and select' })).toBeDisabled();
  });

  it('keeps the dialog open and shows the server message when the save is refused', async () => {
    h.mutate.mockImplementation((_v, o) => o.onError({ response: { data: { detail: { message: 'Choose an active person on this team.' } } } }));
    const onClose = vi.fn();
    open(onClose);
    await userEvent.type(screen.getByLabelText(/Title/), ' v2');
    await userEvent.click(screen.getByRole('button', { name: 'Save and select' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose an active person on this team.');
    expect(onClose).not.toHaveBeenCalled();
  });
});
