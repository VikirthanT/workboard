import type { ImportPreviewRow, ImportRowError } from '../app/types/types';
import type { WireImportPreviewRow } from './backendTypes';
import { apiClient } from './axiosInstance';

/** The filled-in-ready .xlsx: dropdowns come from the team and directory as they are right now. */
export async function downloadImportTemplate(): Promise<Blob> {
  const { data } = await apiClient.get<Blob>('/tasks/import/template', { responseType: 'blob' });
  return data;
}

/** Every check, nothing saved: the tasks the file would add, or a rejection like `uploadTasks`'. */
export async function previewTasks(file: File): Promise<ImportPreviewRow[]> {
  const body = new FormData();
  body.append('file', file);
  const { data } = await apiClient.post<{ tasks: WireImportPreviewRow[] }>('/tasks/import', body, { params: { preview: true } });
  return data.tasks.map((t) => ({
    row: t.row, title: t.title, description: t.description, priority: t.priority, assignee: t.assignee, support: t.support,
    project: t.project, stage: t.stage, startAt: t.start_at, dueAt: t.due_at,
  }));
}

/** All or nothing: resolves with the number of tasks created, or rejects (see `importRowErrors`).
 *  `rows` (sheet row numbers ticked in the preview) adds only those; left out, every row is added. */
export async function uploadTasks(file: File, rows?: number[]): Promise<number> {
  const body = new FormData();
  body.append('file', file);
  const { data } = await apiClient.post<{ created: number }>('/tasks/import', body, { params: { rows: rows?.join(',') } });
  return data.created;
}

/** The per-row problems of a refused upload (`import_invalid`); empty for any other failure. */
export function importRowErrors(err: unknown): ImportRowError[] {
  const detail = (err as { response?: { data?: { detail?: { errors?: ImportRowError[] } } } })?.response?.data?.detail;
  return Array.isArray(detail?.errors) ? detail.errors : [];
}
