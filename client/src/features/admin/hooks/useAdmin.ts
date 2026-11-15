import { keepPreviousData, useMutation, useQueries, useQuery } from '@tanstack/react-query';
import { ADMINS_KEY, getAdminCandidatesKey, getAuditKey, getChannelNameKey, getTeamMembersKey, STANDUP_CHANNELS_KEY, TEAMS_KEY } from '../../../app/constants/queryKeys';
import type { TeamRecord } from '../../../app/types/types';
import {
  changeManager, createTeam, deleteTeam, getAdmins, getAudit, getChannelName, getStandupChannels, getTeamMembers, getTeams, searchPeople, setAdmin,
  setStandupChannel, syncPeople,
} from '../../../services/api';
import { useRefreshTeams } from '../../team/hooks';

export const AUDIT_PAGE_SIZE = 50;

export function useTeams(enabled = true) {
  return useQuery({ queryKey: TEAMS_KEY, queryFn: getTeams, enabled });
}

/** The people of every team at once (a handful of teams, tens of people each), for the admin's grouped list. */
export function useAllTeamMembers(teams: TeamRecord[]) {
  return useQueries({ queries: teams.map((t) => ({ queryKey: getTeamMembersKey(t.id), queryFn: () => getTeamMembers(t.id) })) });
}

/** Everyone with admin access, including admins who are on no team. Kept for the session; an admin change or a people sync refreshes it. */
export function useAdmins(enabled = true) {
  return useQuery({ queryKey: ADMINS_KEY, queryFn: getAdmins, enabled, staleTime: Infinity, gcTime: Infinity });
}

/** People who could be made admin, searched on the server as you type. Loaded only while the picker is open; each search is kept for the session. */
export function useAdminCandidates(enabled: boolean, q: string) {
  return useQuery({
    queryKey: getAdminCandidatesKey(q), queryFn: () => searchPeople(q), enabled, placeholderData: keepPreviousData, staleTime: Infinity, gcTime: Infinity,
  });
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

/**
 * The standup app's channels for the picker. Read once and kept for the whole session (until sign-out or a reload); a
 * suggestions Sync marks it stale, so a channel added to the standup app shows after the next Sync. No retry, since a 501
 * means "not set up".
 */
export function useStandupChannels(enabled: boolean) {
  return useQuery({ queryKey: STANDUP_CHANNELS_KEY, queryFn: getStandupChannels, enabled, retry: false, staleTime: Infinity, gcTime: Infinity });
}

/** The name of one channel id, for the team header and the typed-id hint: the server answers from the standup app's list, then Slack. */
export function useChannelName(channelId: string | null | undefined, enabled = true) {
  const id = (channelId ?? '').trim();
  return useQuery({
    queryKey: getChannelNameKey(id),
    queryFn: () => getChannelName(id),
    enabled: enabled && id.length >= 3,
    retry: false,
    staleTime: Infinity, // a channel's name rarely changes: kept for the session, refreshed by a Sync like the channel list
    gcTime: Infinity,
  });
}

/** Sync the people from Slack. Who is on a team, who can be added and who is active all change, so those lists, the audit log and the boards refetch. */
export function useSyncPeople() {
  return useMutation({ mutationFn: syncPeople, onSuccess: useRefreshTeams() });
}

export function useSetStandupChannel() {
  return useMutation({ mutationFn: setStandupChannel, onSuccess: useRefreshTeams() });
}

export function useSetAdmin() {
  return useMutation({ mutationFn: setAdmin, onSuccess: useRefreshTeams() });
}
