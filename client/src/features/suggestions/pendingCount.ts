import type { SuggestionsPage } from '../../app/types/types';

/** How many suggestions are waiting for the manager's review, across everyone on the team. */
export function pendingCount(page: SuggestionsPage): number {
  return page.people.reduce((n, p) => n + p.suggestions.filter((s) => s.state === 'pending').length, 0);
}
