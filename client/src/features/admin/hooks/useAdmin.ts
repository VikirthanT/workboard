import { keepPreviousData, useMutation, useQueries, useQuery } from '@tanstack/react-query';
import { ADMINS_KEY, getAdminCandidatesKey, getAuditKey, getTeamMembersKey, TEAMS_KEY } from '../../../app/constants/queryKeys';
import type { TeamRecord } from '../../../app/types/types';
import { changeManager, createTeam, deleteTeam, getAdmins, getAudit, getTeamMembers, getTeams, searchPeople, setAdmin } from '../../../services/api';
import { useRefreshTeams } from '../../team/hooks';

export const AUDIT_PAGE_SIZE = 50;

export function useTeams(enabled = true) {
  return useQuery({ queryKey: TEAMS_KEY, queryFn: getTeams, enabled });
}

/** The people of every team at once (a handful of teams, tens of people each), for the admin's grouped list. */
export function useAllTeamMembers(teams: TeamRecord[]) {
  return useQueries({ queries: teams.map((t) => ({ queryKey: getTeamMembersKey(t.id), queryFn: () => getTeamMembers(t.id) })) });
}

/** Everyone with admin access, including admins who are on no team. */
export function useAdmins(enabled = true) {
  return useQuery({ queryKey: ADMINS_KEY, queryFn: getAdmins, enabled });
}

/** People who could be made admin, searched on the server as you type. Loaded only while the picker is open. */
export function useAdminCandidates(enabled: boolean, q: string) {
  return useQuery({ queryKey: getAdminCandidatesKey(q), queryFn: () => searchPeople(q), enabled, placeholderData: keepPreviousData });
}

/** One page of the audit log, newest first. The previous page stays on screen while the next one loads. */
export function useAudit(page: number) {
  const offset = page * AUDIT_PAGE_SIZE;
  return useQuery({
    queryKey: getAuditKey(offset, AUDIT_PAGE_SIZE),
    queryFn: () => getAudit({ limit: AUDIT_PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  });
}

/** Team and admin changes decide who has a board, so the signed-in user's state and the board refetch too. */
export function useCreateTeam() {
  return useMutation({ mutationFn: createTeam, onSuccess: useRefreshTeams() });
}

export function useDeleteTeam() {
  return useMutation({ mutationFn: deleteTeam, onSuccess: useRefreshTeams() });
}

export function useChangeManager() {
  return useMutation({ mutationFn: changeManager, onSuccess: useRefreshTeams() });
}

export function useSetAdmin() {
  return useMutation({ mutationFn: setAdmin, onSuccess: useRefreshTeams() });
}
