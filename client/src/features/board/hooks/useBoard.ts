import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getBoardKey, getPeopleSearchKey, getTaskKey } from '../../../app/constants/queryKeys';
import type { BoardQuery } from '../../../app/types/types';
import { getBoard, getTask, searchPeople } from '../../../services/api';

/** Anyone active in the directory matching `q`, searched on the server; loaded only while the Support picker is open. */
export function usePeopleSearch(enabled: boolean, q: string) {
  return useQuery({ queryKey: getPeopleSearchKey(q), queryFn: () => searchPeople(q), enabled, placeholderData: keepPreviousData });
}

export function useBoard(query: BoardQuery) {
  return useQuery({ queryKey: getBoardKey(query), queryFn: () => getBoard(query), placeholderData: keepPreviousData });
}

export function useTask(id: string | null) {
  return useQuery({ queryKey: getTaskKey(id ?? ''), queryFn: () => getTask(id!), enabled: !!id });
}
