import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getBoardKey, getPeopleSearchKey, getTaskKey } from '../../../app/constants/queryKeys';
import type { BoardQuery, ColumnSizes } from '../../../app/types/types';
import { getBoard, getTask, searchPeople } from '../../../services/api';

/** Anyone active in the directory matching `q`, searched on the server; loaded only while the Support picker is open. */
export function usePeopleSearch(enabled: boolean, q: string) {
  return useQuery({ queryKey: getPeopleSearchKey(q), queryFn: () => searchPeople(q), enabled, placeholderData: keepPreviousData });
}

/** Five minutes: your own changes refresh it at once (the mutations invalidate it); someone else's show on the
 *  next tab focus, a browser reload (the cache is in memory), or at most five minutes later. Shorten when Slack changes cards (Phase 2). */
const BOARD_FRESH_MS = 5 * 60 * 1000;

export function useBoard(query: BoardQuery, sizes: ColumnSizes) {
  return useQuery({
    queryKey: getBoardKey(query, sizes),
    queryFn: () => getBoard(query, sizes),
    placeholderData: keepPreviousData,
    staleTime: BOARD_FRESH_MS,
    refetchInterval: BOARD_FRESH_MS,
  });
}

export function useTask(id: string | null) {
  return useQuery({ queryKey: getTaskKey(id ?? ''), queryFn: () => getTask(id!), enabled: !!id });
}
