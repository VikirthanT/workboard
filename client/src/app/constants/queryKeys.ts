import type { BoardQuery } from '../types/types';

export const ME_KEY = ['me'] as const;
export const BOARD_KEY = ['board'] as const;
export const getBoardKey = (q: BoardQuery) => [...BOARD_KEY, q] as const;
export const REPORT_KEY = ['report'] as const;
export const getReportKey = (q: BoardQuery, from: string, to: string) => [...REPORT_KEY, q, from, to] as const;
export const getAllTeamsReportKey = (from: string, to: string) => [...REPORT_KEY, 'all-teams', from, to] as const;
export const TASK_KEY = ['task'] as const;
export const getTaskKey = (id: string) => [...TASK_KEY, id] as const;
export const TEAMS_KEY = ['teams'] as const;
export const getTeamMembersKey = (id: string) => [...TEAMS_KEY, id, 'members'] as const;
export const UNASSIGNED_KEY = ['people', 'unassigned'] as const;
export const getUnassignedKey = (q: string) => [...UNASSIGNED_KEY, q] as const;
export const ADMINS_KEY = ['admins'] as const;
export const getAdminCandidatesKey = (q: string) => [...ADMINS_KEY, 'candidates', q] as const;
export const AUDIT_KEY = ['audit'] as const;
export const getAuditKey = (offset: number, limit: number) => [...AUDIT_KEY, offset, limit] as const;
