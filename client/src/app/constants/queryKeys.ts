import type { BoardQuery, ColumnSizes } from '../types/types';

export const ME_KEY = ['me'] as const;
export const BOARD_KEY = ['board'] as const;
export const getBoardKey = (q: BoardQuery, sizes: ColumnSizes) => [...BOARD_KEY, q, sizes] as const;
export const REPORT_KEY = ['report'] as const;
export const getReportKey = (q: BoardQuery, from: string, to: string) => [...REPORT_KEY, q, from, to] as const;
export const getAllTeamsReportKey = (from: string, to: string) => [...REPORT_KEY, 'all-teams', from, to] as const;
export const TASK_KEY = ['task'] as const;
export const getTaskKey = (id: string) => [...TASK_KEY, id] as const;
export const TEAMS_KEY = ['teams'] as const;
export const getTeamMembersKey = (id: string) => [...TEAMS_KEY, id, 'members'] as const;
export const STANDUP_CHANNELS_KEY = ['standups', 'channels'] as const;
export const getChannelNameKey = (id: string) => [...STANDUP_CHANNELS_KEY, 'name', id] as const;
export const getChannelMembersKey = (teamId: string) => [...TEAMS_KEY, teamId, 'channel-members'] as const;
export const SUGGESTIONS_KEY = ['suggestions'] as const;
export const getSuggestionsKey = (teamId: string) => [...SUGGESTIONS_KEY, teamId] as const;
/** Every cached list of people from the directory (the "Add person" picker, the Support picker): one key to refresh them all. */
export const PEOPLE_KEY = ['people'] as const;
export const UNASSIGNED_KEY = [...PEOPLE_KEY, 'unassigned'] as const;
export const getUnassignedKey = (q: string) => [...UNASSIGNED_KEY, q] as const;
export const getPeopleSearchKey = (q: string) => [...PEOPLE_KEY, 'search', q] as const;
export const ADMINS_KEY = ['admins'] as const;
export const getAdminCandidatesKey = (q: string) => [...ADMINS_KEY, 'candidates', q] as const;
export const AUDIT_KEY = ['audit'] as const;
export const getAuditKey = (offset: number, limit: number) => [...AUDIT_KEY, offset, limit] as const;
