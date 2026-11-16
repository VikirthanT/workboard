import { describe, expect, it } from 'vitest';
import type { PersonSuggestions, Suggestion, SuggestionsPage } from '../../app/types/types';
import { pendingCount } from './pendingCount';

const suggestion = (state: Suggestion['state']): Suggestion => ({
  id: state, personId: 'p', title: 't', description: 'd', kind: 'new', priority: 'medium', startAt: null, dueAt: null, dueIsDefault: false,
  subtasks: [], evidenceQuote: 'a line from it', relatedTo: null, state, lateReply: false, standupDate: '2026-11-09', taskId: null,
});
const person = (...states: Suggestion['state'][]): PersonSuggestions => ({
  person: { id: 'p', displayName: 'P', email: 'p@example.test', role: 'member' }, standup: null, suggestions: states.map(suggestion),
});
const page = (...people: PersonSuggestions[]): SuggestionsPage => ({ standupChannelId: 'C0TEST', lastSyncedAt: null, standupProblem: null, people });

describe('pendingCount', () => {
  it('counts only the pending ones, across everyone', () => {
    expect(pendingCount(page(person('pending', 'approved'), person('rejected', 'pending', 'pending')))).toBe(3);
  });

  it('is zero for an empty team or when nothing is pending', () => {
    expect(pendingCount(page())).toBe(0);
    expect(pendingCount(page(person('approved', 'rejected'), person()))).toBe(0);
  });
});
