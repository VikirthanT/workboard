import type { ImportRowError } from '../app/types/types';
import { apiClient } from './axiosInstance';

/** The filled-in-ready .xlsx: dropdowns come from the team and directory as they are right now. */
export async function downloadImportTemplate(): Promise<Blob> {
  const { data } = await apiClient.get<Blob>('/tasks/import/template', { responseType: 'blob' });
  return data;
}

/** All or nothing: resolves with the number of tasks created, or rejects (see `importRowErrors`). */
export async function uploadTasks(file: File): Promise<number> {
  const body = new FormData();
  body.append('file', file);
  const { data } = await apiClient.post<{ created: number }>('/tasks/import', body);
  return data.created;
}

/** The per-row problems of a refused upload (`import_invalid`); empty for any other failure. */
export function importRowErrors(err: unknown): ImportRowError[] {
  const detail = (err as { response?: { data?: { detail?: { errors?: ImportRowError[] } } } })?.response?.data?.detail;
  return Array.isArray(detail?.errors) ? detail.errors : [];
}
