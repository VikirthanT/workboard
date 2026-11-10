import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BOARD_KEY, ME_KEY, TASK_KEY } from '../../../app/constants/queryKeys';
import type { Board, Status, TaskInput } from '../../../app/types/types';
import { addComment, createTask, deleteTask, moveTask, previewTasks, updateTask, uploadTasks } from '../../../services/api';

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

/** Checks the file and lists what it would add; saves nothing, so nothing to refresh. */
export function usePreviewImport() {
  return useMutation({ mutationFn: (file: File) => previewTasks(file) });
}

export function useImportTasks() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { file: File; rows?: number[] }) => uploadTasks(v.file, v.rows), onSuccess: refresh });
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

/** The card jumps to its new column at once; the refetch after (success or failure) puts the server's truth back. */
export function useMoveTask() {
  const qc = useQueryClient();
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (v: { id: string; to: Status; note?: string; completedOn?: string }) => moveTask(v.id, v.to, v.note, v.completedOn),
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: BOARD_KEY }); // a load in flight would overwrite the move with the old column
      qc.setQueriesData<Board>({ queryKey: BOARD_KEY }, (board) =>
        board && { ...board, tasks: board.tasks.map((t) => (t.id === v.id ? { ...t, status: v.to } : t)) },
      );
    },
    onSettled: refresh,
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
