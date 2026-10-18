import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BOARD_KEY, ME_KEY, TASK_KEY } from '../../../app/constants/queryKeys';
import type { Status, TaskInput } from '../../../app/types/types';
import { addComment, createTask, deleteTask, moveTask, updateTask } from '../../../services/api';

/** Every task change can move cards, header counts and an open detail panel. */
function useRefresh() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: BOARD_KEY }),
      qc.invalidateQueries({ queryKey: TASK_KEY }),
      qc.invalidateQueries({ queryKey: ME_KEY }),
    ]);
}

export function useCreateTask() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (i: TaskInput) => createTask(i), onSuccess: refresh });
}

export function useUpdateTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (v: { id: string; patch: Partial<TaskInput> }) => updateTask(v.id, v.patch),
    onSuccess: refresh,
  });
}

export function useDeleteTask() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (id: string) => deleteTask(id), onSuccess: refresh });
}

export function useMoveTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (v: { id: string; to: Status; note?: string; completedOn?: string }) => moveTask(v.id, v.to, v.note, v.completedOn),
    onSuccess: refresh,
  });
}

/** A comment only changes the open task's timeline, not the board or header counts. */
export function useAddComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; body: string }) => addComment(v.id, v.body),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASK_KEY }),
  });
}
