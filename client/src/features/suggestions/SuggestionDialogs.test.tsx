import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { addDays, todayISO } from '../../app/domain/dates';
import type { Suggestion } from '../../app/types/types';
import { AddSuggestionsDialog } from './AddSuggestionsDialog';
import { EditSuggestionDialog } from './EditSuggestionDialog';

const h = vi.hoisted(() => ({ mutate: vi.fn() }));
vi.mock('./hooks', () => ({
  useAddSuggestions: () => ({ mutate: h.mutate, isPending: false }),
  useEditSuggestion: () => ({ mutate: h.mutate, isPending: false }),
}));
// The calendar has its own tests; here a plain box stands in so a test can type a date.
vi.mock('../../app/components/ui/date-picker', () => ({
  DatePicker: ({ id, value, onChange }: { id?: string; value: string; onChange: (v: string) => void }) => (
    <input id={id} aria-label={`date ${id}`} value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

const TODAY = todayISO();
const suggestion = (over: Partial<Suggestion>): Suggestion => ({
  id: 's1', personId: 'p-ravi', title: 'Design weld jig', description: 'The jig design is ready.', kind: 'new', priority: 'medium',
  startAt: TODAY, dueAt: addDays(TODAY, 3), dueIsDefault: true, subtasks: [], evidenceQuote: 'Start the weld jig design', relatedTo: null,
  state: 'pending', lateReply: false, standupDate: TODAY, taskId: null, ...over,
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
    h.mutate.mockImplementation((_v, o) => o.onSuccess());
    open(onClose, onAdded);
    await userEvent.click(screen.getByRole('checkbox', { name: /Order bracket samples/ }));
    expect(screen.getByText('Add 2 tasks')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Create (2)' }));
    expect(h.mutate).toHaveBeenCalledWith(
      { suggestionIds: ['s1', 's3'], dueDates: { s1: addDays(TODAY, 3), s3: addDays(TODAY, 3) } },
      expect.anything(),
    );
    expect(onAdded).toHaveBeenCalledWith(2);
    expect(onClose).toHaveBeenCalled();
  });

  describe('the due date is compulsory', () => {
    const undated = [{ person: ravi, suggestions: [suggestion({ id: 's1', dueAt: null }), suggestion({ id: 's2', title: 'Order bracket samples' })] }];
    const openUndated = (onAdded = vi.fn()) => render(<AddSuggestionsDialog teamId="t1" groups={undated} onClose={vi.fn()} onAdded={onAdded} />);

    it('cannot create while a task has no due date, and says which still need one', () => {
      openUndated();

      expect(screen.getByRole('button', { name: 'Create (2)' })).toBeDisabled();
      expect(screen.getByText(/1 still needs a due date: every task must have one\./)).toBeInTheDocument();
      expect(screen.getByText('Choose a due date.')).toBeInTheDocument();
      expect(screen.getByLabelText('date due-s2')).toHaveValue(addDays(TODAY, 3)); // the one that has a date shows it, editable
    });

    it('creates once the missing date is entered, sending it with the others', async () => {
      h.mutate.mockImplementation((_v, o) => o.onSuccess());
      const onAdded = vi.fn();
      openUndated(onAdded);

      await userEvent.type(screen.getByLabelText('date due-s1'), addDays(TODAY, 5));

      expect(screen.getByRole('button', { name: 'Create (2)' })).toBeEnabled();
      expect(screen.queryByText('Choose a due date.')).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Create (2)' }));
      expect(h.mutate.mock.calls[0][0]).toEqual({ suggestionIds: ['s1', 's2'], dueDates: { s1: addDays(TODAY, 5), s2: addDays(TODAY, 3) } });
      expect(onAdded).toHaveBeenCalledWith(2);
    });

    it('does not ask for a date on a task that is unticked', async () => {
      openUndated();

      await userEvent.click(screen.getByRole('checkbox', { name: /Design weld jig/ }));

      expect(screen.getByRole('button', { name: 'Create (1)' })).toBeEnabled(); // the dated one alone
      expect(screen.queryByLabelText('date due-s1')).not.toBeInTheDocument();
    });

    it('asks for a new date when the suggestion\'s own has already passed', () => {
      const stale = [{ person: ravi, suggestions: [suggestion({ id: 's1', dueAt: addDays(TODAY, -2) })] }];
      render(<AddSuggestionsDialog teamId="t1" groups={stale} onClose={vi.fn()} onAdded={vi.fn()} />);

      expect(screen.getByText('That date has passed. Choose a new one.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Create (1)' })).toBeDisabled();
    });
  });

  it('cannot create when nothing is ticked', async () => {
    open();
    for (const box of screen.getAllByRole('checkbox')) await userEvent.click(box);
    expect(screen.getByText('Nothing is ticked, so nothing will be created.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create (0)' })).toBeDisabled();
  });

  it('shows the server message, which names the suggestion that broke a rule', async () => {
    h.mutate.mockImplementation((_v, o) => o.onError({ response: { data: { detail: { message: '“Design weld jig”: The due date cannot be in the past.' } } } }));
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
