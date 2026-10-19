import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { BoardFilter, BoardQuery } from '../../../app/types/types';

const FILTERS: BoardFilter[] = ['overdue', 'due_week', 'blocked', 'needs_review'];

interface View {
  attention: boolean;
  personId: string | null;
  filters: BoardFilter[];
  taskId: string | null;
}

const EMPTY: View = { attention: false, personId: null, filters: [], taskId: null };

function load(key: string): View {
  try {
    const v = { ...EMPTY, ...JSON.parse(sessionStorage.getItem(key) ?? '{}') };
    return { ...v, filters: v.filters.filter((f: BoardFilter) => FILTERS.includes(f)) };
  } catch {
    return EMPTY;
  }
}

/**
 * The URL is only the page (`/`, `/boards/npi`): no ids, no filters. The view (attention tick, person, filters, open task)
 * is kept per team in sessionStorage, so a refresh or a trip to another page brings it back; it ends with the tab.
 * The header's "Needs review" link is the one exception: `/?filter=needs_review` is applied once, then dropped from the URL.
 * Nothing here grants access: the server checks every request.
 */
export function useBoardParams(teamId: string | null = null) {
  const key = `wb_board:${teamId ?? 'own'}`;
  const [view, setView] = useState<View>(() => load(key));
  const [params, setParams] = useSearchParams();

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(view));
    } catch {
      /* storage blocked: the view just won't survive a refresh */
    }
  }, [key, view]);

  useEffect(() => {
    const f = params.get('filter');
    if (!f) return;
    setView((v) => ({ ...v, filters: FILTERS.includes(f as BoardFilter) ? [f as BoardFilter] : v.filters }));
    setParams({}, { replace: true });
  }, [params, setParams]);

  const patch = (changes: Partial<View>) => setView((v) => ({ ...v, ...changes }));

  // Admins pick a team (the `/boards/<team-name>` path, resolved by the caller); for a manager the server always answers with their own.
  const query: BoardQuery = useMemo(
    () => ({ teamId, attention: view.attention, personId: view.personId, filters: view.filters }),
    [teamId, view.attention, view.personId, view.filters],
  );

  return {
    query,
    taskId: view.taskId,
    setAttention: (attention: boolean) => patch({ attention }),
    setPerson: (personId: string | null) => patch({ personId }),
    toggleFilter: (f: BoardFilter) => patch({ filters: view.filters.includes(f) ? view.filters.filter((x) => x !== f) : [...view.filters, f] }),
    clearFilters: () => patch({ filters: [] }),
    openTask: (taskId: string | null) => patch({ taskId }),
  };
}
