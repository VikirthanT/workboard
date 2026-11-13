import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getBoardKey, getPeopleSearchKey, getTaskKey } from '../../../app/constants/queryKeys';
import type { BoardQuery, ColumnSizes } from '../../../app/types/types';
import { getBoard, getTask, searchPeople } from '../../../services/api';

/** Anyone active in the directory matching `q`, searched on the server; loaded only while the Support picker is open. */
export function usePeopleSearch(enabled: boolean, q: string) {
  return useQuery({ queryKey: getPeopleSearchKey(q), queryFn: () => searchPeople(q), enabled, placeholderData: keepPreviousData });
}

/** Ten seconds: your own changes refresh it at once (the mutations invalidate it); a change made elsewhere, by Slack or by
 *  another manager, shows within ten seconds while the tab is visible (a hidden tab does not poll), and at once on tab focus.
 *  Polling, not a push: simple, and a handful of managers is a light load. */
const BOARD_FRESH_MS = 10 * 1000;

export function useBoard(query: BoardQuery, sizes: ColumnSizes) {
  return useQuery({
    queryKey: getBoardKey(query, sizes),
    queryFn: () => getBoard(query, sizes),
    placeholderData: keepPreviousData,
    staleTime: BOARD_FRESH_MS,
    refetchInterval: BOARD_FRESH_MS,
  });
}

/** The open task and its timeline and comments: refetched every ten seconds while it is open, so a comment or a status
 *  change made in Slack appears without reloading. */
export function useTask(id: string | null) {
  return useQuery({ queryKey: getTaskKey(id ?? ''), queryFn: () => getTask(id!), enabled: !!id, refetchInterval: BOARD_FRESH_MS });
}
