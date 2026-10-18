import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { BoardFilter, BoardQuery } from '../../../app/types/types';

const FILTERS: BoardFilter[] = ['overdue', 'due_week', 'blocked', 'needs_review'];

/**
 * Board state lives in the URL, so the header's review badge can deep-link
 * ("/?filter=needs_review"), a link can open a task ("/?task=..."), and a refresh keeps your view.
 */
export function useBoardParams() {
  const [params, setParams] = useSearchParams();

  const query: BoardQuery = useMemo(
    () => ({
      // Admins pick a team; for a manager the server always answers with their own.
      teamId: params.get('team'),
      // The board opens on every task; "Needs attention" (?attention=1) narrows the cards.
      attention: params.get('attention') === '1',
      personId: params.get('person'),
      filters: (params.get('filter') ?? '').split(',').filter((f): f is BoardFilter => FILTERS.includes(f as BoardFilter)),
    }),
    [params],
  );

  const taskId = params.get('task');

  const patch = useCallback(
    (changes: Record<string, string | null>, replace = true) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          Object.entries(changes).forEach(([k, v]) => (v === null || v === '' ? next.delete(k) : next.set(k, v)));
          return next;
        },
        { replace },
      ),
    [setParams],
  );

  return {
    query,
    taskId,
    /** Switching team drops the person, filters and open task, which belong to the old team. */
    setTeam: (id: string) => patch({ team: id, person: null, filter: null, task: null }),
    setAttention: (on: boolean) => patch({ attention: on ? '1' : null }),
    setPerson: (id: string | null) => patch({ person: id }),
    toggleFilter: (f: BoardFilter) =>
      patch({ filter: (query.filters.includes(f) ? query.filters.filter((x) => x !== f) : [...query.filters, f]).join(',') || null }),
    clearFilters: () => patch({ filter: null }),
    openTask: (id: string | null) => patch({ task: id }, false),
  };
}
