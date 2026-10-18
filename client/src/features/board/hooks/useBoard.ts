import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getBoardKey, getTaskKey } from '../../../app/constants/queryKeys';
import type { BoardQuery } from '../../../app/types/types';
import { getBoard, getTask } from '../../../services/api';

export function useBoard(query: BoardQuery) {
  return useQuery({ queryKey: getBoardKey(query), queryFn: () => getBoard(query), placeholderData: keepPreviousData });
}

export function useTask(id: string | null) {
  return useQuery({ queryKey: getTaskKey(id ?? ''), queryFn: () => getTask(id!), enabled: !!id });
}
