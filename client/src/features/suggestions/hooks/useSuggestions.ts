import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BOARD_KEY, getSuggestionsKey, ME_KEY, REPORT_KEY, STANDUP_CHANNELS_KEY, SUGGESTIONS_KEY, TASK_KEY } from '../../../app/constants/queryKeys';
import type { SuggestionPatch, SuggestionsPage } from '../../../app/types/types';
import { addSuggestions, editSuggestion, getSuggestions, rejectSuggestion, restoreSuggestion, suggestTasks, syncSuggestions } from '../../../services/api';
import { pendingCount } from '../pendingCount';

/**
 * The page for a team: each person with their latest standup and suggestions. It reads the standup database on the server,
 * so it is read once and kept for the whole session (until sign-out or a reload); only a Sync, or a change the manager makes
 * to a suggestion, replaces it. A scheduled sync on the server therefore shows after a reload or the next Sync.
 */
export function useSuggestions(teamId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: getSuggestionsKey(teamId ?? ''),
    queryFn: () => getSuggestions(teamId!),
    enabled: enabled && !!teamId,
    staleTime: Infinity,
    gcTime: Infinity, // kept even while the page is closed
    refetchOnWindowFocus: false,
  });
}

/** Just the number of suggestions waiting for review, for the header badge. Shares the cache with `useSuggestions`. */
export function usePendingSuggestionCount(teamId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: getSuggestionsKey(teamId ?? ''),
    queryFn: () => getSuggestions(teamId!),
    enabled: enabled && !!teamId,
    staleTime: Infinity,
    gcTime: Infinity,
    refetchOnWindowFocus: false,
    select: pendingCount,
  });
}

/** A sync returns the fresh page, so it replaces the cached one instead of triggering another read. It reads the whole team. */
export function useSyncSuggestions(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => syncSuggestions({ teamId }),
    onSuccess: (page: SuggestionsPage) => {
      qc.setQueryData(getSuggestionsKey(teamId), page);
      // The standup app may have gained channels since the list was last read: the pickers read it again.
      void qc.invalidateQueries({ queryKey: STANDUP_CHANNELS_KEY });
    },
  });
}

/** Ask the model for tasks from one person's posts (or, with nothing, everyone's). The reply is the fresh page. */
export function useSuggestTasks(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (personId?: string) => suggestTasks({ teamId, personId }),
    onSuccess: (page: SuggestionsPage) => qc.setQueryData(getSuggestionsKey(teamId), page),
  });
}

/** Adding creates tasks, so the board, the open task, the signed-in user's counts and the report refetch too. */
export function useAddSuggestions(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { suggestionIds: string[]; dueDates: Record<string, string> }) => addSuggestions({ teamId, ...v }),
    onSuccess: (page: SuggestionsPage) => {
      qc.setQueryData(getSuggestionsKey(teamId), page);
      return Promise.all([BOARD_KEY, TASK_KEY, ME_KEY, REPORT_KEY].map((queryKey) => qc.invalidateQueries({ queryKey })));
    },
  });
}

function useRefreshSuggestions() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: SUGGESTIONS_KEY });
}

export function useEditSuggestion() {
  return useMutation({ mutationFn: (v: { id: string; patch: SuggestionPatch }) => editSuggestion(v), onSuccess: useRefreshSuggestions() });
}

export function useRejectSuggestion() {
  return useMutation({ mutationFn: (id: string) => rejectSuggestion(id), onSuccess: useRefreshSuggestions() });
}

export function useRestoreSuggestion() {
  return useMutation({ mutationFn: (id: string) => restoreSuggestion(id), onSuccess: useRefreshSuggestions() });
}
