import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BOARD_KEY, getSuggestionsKey, ME_KEY, REPORT_KEY, STANDUP_CHANNELS_KEY, SUGGESTIONS_KEY, TASK_KEY } from '../../../app/constants/queryKeys';
import type { SuggestionPatch, SuggestionsPage } from '../../../app/types/types';
import { addSuggestions, editSuggestion, getSuggestions, rejectSuggestion, restoreSuggestion, syncSuggestions } from '../../../services/api';
import { pendingCount } from '../pendingCount';

/** The page for a team: each person with their latest standup and suggestions. Reads the standup database on the server, so it is not refetched on every focus. */
export function useSuggestions(teamId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: getSuggestionsKey(teamId ?? ''),
    queryFn: () => getSuggestions(teamId!),
    enabled: enabled && !!teamId,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

/** Just the number of suggestions waiting for review, for the header badge. Shares the cache with `useSuggestions`. */
export function usePendingSuggestionCount(teamId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: getSuggestionsKey(teamId ?? ''),
    queryFn: () => getSuggestions(teamId!),
    enabled: enabled && !!teamId,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    select: pendingCount,
  });
}

/**
 * A sync returns the fresh page, so it replaces the cached one instead of triggering another read. Call it with a
 * person's id to sync only them (one at a time), or with nothing to sync everyone.
 */
export function useSyncSuggestions(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (personId?: string) => syncSuggestions({ teamId, personId }),
    onSuccess: (page: SuggestionsPage) => {
      qc.setQueryData(getSuggestionsKey(teamId), page);
      // The standup app may have gained channels since the list was last read: the pickers read it again.
      void qc.invalidateQueries({ queryKey: STANDUP_CHANNELS_KEY });
    },
  });
}

/** Adding creates tasks, so the board, the open task, the signed-in user's counts and the report refetch too. */
export function useAddSuggestions(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (suggestionIds: string[]) => addSuggestions({ teamId, suggestionIds }),
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
