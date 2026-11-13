import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { PersonSuggestions, StandupPost, Suggestion } from '../../app/types/types';
import { SuggestionsView } from './SuggestionsView';

const h = vi.hoisted(() => ({
  me: undefined as unknown,
  page: {} as Record<string, unknown>,
  sync: vi.fn(),
  reject: vi.fn(),
  restore: vi.fn(),
  toast: vi.fn(),
}));
vi.mock('../../hooks', () => ({ useCurrentUser: () => ({ data: h.me }) }));
vi.mock('./hooks', () => ({
  useSuggestions: () => h.page,
  useSyncSuggestions: () => ({ mutate: h.sync, isPending: false }),
  useRejectSuggestion: () => ({ mutate: h.reject, isPending: false }),
  useRestoreSuggestion: () => ({ mutate: h.restore, isPending: false }),
}));
vi.mock('../../app/components/ui/toast', () => ({ useToast: () => ({ toast: h.toast }) }));
// The dialogs have their own tests; here they only need to show that the page opened them with the right things.
vi.mock('./EditSuggestionDialog', () => ({ EditSuggestionDialog: ({ suggestion }: { suggestion: Suggestion | null }) => suggestion && <div>edit-open {suggestion.title}</div> }));
vi.mock('./AddSuggestionsDialog', () => ({
  AddSuggestionsDialog: ({ groups }: { groups: { person: { displayName: string }; suggestions: Suggestion[] }[] }) => (
    <div>add-open {groups.map((g) => `${g.person.displayName}:${g.suggestions.length}`).join(',')}</div>
  ),
}));

const manager = { isManager: true, isAdmin: false, team: { id: 't1', name: 'NPI' }, user: { id: 'u1' } };
const suggestion = (over: Partial<Suggestion>): Suggestion => ({
  id: 's', personId: 'p-ravi', title: 'Design weld jig', description: 'The jig design is ready.', kind: 'new', priority: 'medium',
  startAt: '2026-11-09', dueAt: '2026-11-13', dueIsDefault: true, subtasks: [], evidenceQuote: 'Start the weld jig design', relatedTo: null,
  state: 'pending', lateReply: false, standupDate: '2026-11-09', taskId: null, ...over,
});
const post = (over: Partial<StandupPost> = {}): StandupPost => ({
  date: '2026-11-09', postedAt: '2026-11-11T12:00:00Z', lateReply: false, lastWeek: 'Finished drawings', thisWeek: 'Weld jig work', blockers: null, message: null, ...over,
});
const entry = (id: string, name: string, standup: StandupPost | null, suggestions: Suggestion[]): PersonSuggestions => ({
  person: { id, displayName: name, email: `${name.toLowerCase()}@example.test`, role: 'member' }, standup, suggestions,
});

const ravi = entry('p-ravi', 'Ravi', post({ lateReply: true, blockers: 'Waiting on parts' }), [
  suggestion({ id: 's1', title: 'Design weld jig' }),
  suggestion({ id: 's2', title: 'Order bracket samples', description: 'Samples are ordered.', priority: 'high', relatedTo: 'Existing order', state: 'rejected' }),
  suggestion({ id: 's3', title: 'Release harness drawing', description: 'The drawing is released.', state: 'approved' }),
]);
const asha = entry('p-asha', 'Asha', post({ thisWeek: 'Review the test plan', lateReply: false }), []);
const divya = entry('p-divya', 'Divya', null, []);

const loaded = (people: PersonSuggestions[], over: Record<string, unknown> = {}) =>
  ({ data: { people, standupChannelId: 'C0NPI', lastSyncedAt: '2026-11-13T04:12:00Z', standupProblem: null, ...over }, isError: false, error: null });

beforeEach(() => {
  h.me = manager;
  h.page = loaded([asha, ravi, divya]);
  Object.values(h).forEach((v) => typeof v === 'function' && (v as ReturnType<typeof vi.fn>).mockReset?.());
});

describe('SuggestionsView', () => {
  it('tells a non-manager the page is for managers', () => {
    h.me = { ...manager, isManager: false };
    render(<SuggestionsView />);
    expect(screen.getByText('Suggestions are for team managers')).toBeInTheDocument();
  });

  it('says when the team has no standup channel, and cannot sync', () => {
    h.page = loaded([asha], { standupChannelId: null });
    render(<SuggestionsView />);
    expect(screen.getByText('No standup channel yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sync now/ })).toBeDisabled();
  });

  it('explains when the standup posts cannot be read, instead of saying nobody posted, and still shows the suggestions', () => {
    h.page = loaded([asha, ravi, divya].map((e) => ({ ...e, standup: null })), { standupProblem: 'not_configured' });
    render(<SuggestionsView />);
    expect(screen.getByText('The standup posts cannot be shown')).toBeInTheDocument();
    expect(screen.getByText(/standup database is not set up on this server/)).toBeInTheDocument();
    expect(screen.queryByText('No standup posted recently.')).not.toBeInTheDocument();
    expect(screen.getByText('Design weld jig')).toBeInTheDocument(); // the suggestions we already hold are still there
  });

  it('says when the team\'s channel has no posts at all, which usually means the wrong channel id', () => {
    h.page = loaded([asha, ravi, divya].map((e) => ({ ...e, standup: null })), { standupProblem: 'channel_empty', standupChannelId: 'C0WRONG' });
    render(<SuggestionsView />);
    expect(screen.getByText('No standup posts found in this team’s channel')).toBeInTheDocument();
    expect(screen.getByText(/C0WRONG/)).toBeInTheDocument();
    expect(screen.getAllByText('No standup posted recently.').length).toBeGreaterThan(0); // each person still says so
  });

  it('shows the error when the page cannot load', () => {
    h.page = { data: undefined, isError: true, error: { message: 'Boom' } };
    render(<SuggestionsView />);
    expect(screen.getByText('Could not load suggestions')).toBeInTheDocument();
  });

  it('lists each person with when they posted and a chip for a late reply or a blocker', () => {
    render(<SuggestionsView />);
    const list = within(screen.getByRole('navigation', { name: 'Team members' }));
    const row = (name: string) => list.getByRole('button', { name: new RegExp(name) });
    expect(within(row('Ravi')).getByText('Posted Wed 11 Nov')).toBeInTheDocument();
    expect(within(row('Ravi')).getByText('Late reply')).toBeInTheDocument();
    expect(within(row('Ravi')).getByText('Has a blocker')).toBeInTheDocument();
    expect(within(row('Asha')).queryByText('Late reply')).not.toBeInTheDocument();
    expect(within(row('Divya')).getByText('No standup this week')).toBeInTheDocument();
    expect(screen.getByText(/Last sync 13 Nov/)).toBeInTheDocument();
  });

  it('opens on the first person with suggestions waiting, and switching shows the other person\'s standup', async () => {
    render(<SuggestionsView />);
    expect(screen.getByText('Design weld jig')).toBeInTheDocument(); // Ravi, not Asha who is first in the list
    expect(screen.getByText('Waiting on parts')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Asha/ }));
    expect(screen.getByText('Review the test plan')).toBeInTheDocument();
    expect(screen.getByText('No suggestions for Asha.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Divya/ }));
    expect(screen.getByText('No standup posted recently.')).toBeInTheDocument();
  });

  it('shows each card with its description, quote and default due date, and what state it is in', () => {
    render(<SuggestionsView />);
    const card = within(screen.getByText('Design weld jig').closest('article')!);
    expect(card.getByText('The jig design is ready.')).toBeInTheDocument();
    expect(card.getByText(/Start the weld jig design/)).toBeInTheDocument();
    expect(card.getByText(/Due Fri 13 Nov \(default\)/)).toBeInTheDocument();
    expect(screen.getByText('Rejected')).toBeInTheDocument();
    expect(screen.getByText('Added to board')).toBeInTheDocument();
    expect(screen.getByText('Related to: Existing order')).toBeInTheDocument();
  });

  it('shows the ones still to decide first, then rejected, and the ones already added at the bottom', () => {
    h.page = loaded([entry('p-ravi', 'Ravi', post(), [
      suggestion({ id: 'a', title: 'Already added', description: 'd1', state: 'approved' }),
      suggestion({ id: 'r', title: 'Was rejected', description: 'd2', state: 'rejected' }),
      suggestion({ id: 'p1', title: 'Waiting one', description: 'd3' }),
      suggestion({ id: 'p2', title: 'Waiting two', description: 'd4' }),
    ])]);
    render(<SuggestionsView />);
    const titles = screen.getAllByRole('article').map((card) => within(card).getAllByText(/Waiting|rejected|added/)[0].textContent);
    expect(titles).toEqual(['Waiting one', 'Waiting two', 'Was rejected', 'Already added']);
  });

  it('selecting a card enables Add with the count, and Add opens the review with the ticked ones', async () => {
    render(<SuggestionsView />);
    expect(screen.getByRole('button', { name: 'Add (0)' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Select' }));
    expect(screen.getByText('Selected to add')).toBeInTheDocument();
    expect(screen.getByText('1 selected')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Add (1)' }));
    expect(screen.getByText('add-open Ravi:1')).toBeInTheDocument();
  });

  it('opens the edit dialog for the chosen card', async () => {
    render(<SuggestionsView />);
    await userEvent.click(screen.getByRole('button', { name: /Edit/ }));
    expect(screen.getByText('edit-open Design weld jig')).toBeInTheDocument();
  });

  it('rejects and restores, and only a pending card has Select, Edit and Reject', async () => {
    render(<SuggestionsView />);
    expect(screen.getAllByRole('button', { name: 'Select' })).toHaveLength(1);
    await userEvent.click(screen.getByRole('button', { name: /Reject/ }));
    expect(h.reject).toHaveBeenCalledWith('s1', expect.anything());
    await userEvent.click(screen.getByRole('button', { name: /Restore/ }));
    expect(h.restore).toHaveBeenCalledWith('s2', expect.anything());
  });

  it('syncs everyone on demand, or one person at a time', async () => {
    render(<SuggestionsView />);
    await userEvent.click(screen.getByRole('button', { name: /Sync now/ }));
    expect(h.sync).toHaveBeenLastCalledWith(undefined, expect.anything());
    await userEvent.click(screen.getByRole('button', { name: 'Sync Ravi' })); // Ravi is the open person
    expect(h.sync).toHaveBeenLastCalledWith('p-ravi', expect.anything());
    await userEvent.click(screen.getByRole('button', { name: /Asha/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Sync Asha' }));
    expect(h.sync).toHaveBeenLastCalledWith('p-asha', expect.anything());
  });
});
