import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ADMINS_KEY, AUDIT_KEY, BOARD_KEY, ME_KEY, TEAMS_KEY, UNASSIGNED_KEY, getChannelMembersKey, getTeamMembersKey, getUnassignedKey } from '../../../app/constants/queryKeys';
import { addMember, addMembers, getChannelMembers, getTeamMembers, removeMember, searchUnassignedPeople } from '../../../services/api';

/** A team's people, manager first. Admins can open any team; a manager only their own. */
export function useTeamMembers(teamId: string | null) {
  return useQuery({ queryKey: getTeamMembersKey(teamId ?? ''), queryFn: () => getTeamMembers(teamId!), enabled: !!teamId });
}

/** People who can still join a team (on none yet) matching `q`, searched on the server. Loaded only while the picker is open. */
export function useUnassignedPeople(enabled: boolean, q: string) {
  return useQuery({ queryKey: getUnassignedKey(q), queryFn: () => searchUnassignedPeople(q), enabled, placeholderData: (previous) => previous });
}

/** A membership change moves who can be assigned, so the board, header counts and audit refetch too. */
export function useRefreshTeams() {
  const qc = useQueryClient();
  return () => Promise.all([TEAMS_KEY, UNASSIGNED_KEY, ADMINS_KEY, AUDIT_KEY, BOARD_KEY, ME_KEY].map((k) => qc.invalidateQueries({ queryKey: k })));
}

export function useAddMember(teamId: string) {
  const refresh = useRefreshTeams();
  return useMutation({ mutationFn: (v: { personId: string; reason: string }) => addMember({ teamId, ...v }), onSuccess: refresh });
}

/** Who is in the team's Slack channel, read when the review opens (never cached: it is a live look at Slack). No retry: the
 *  server's answer ("no channel set", "channel not found", "invite the bot") is what the dialog shows. */
export function useChannelMembers(teamId: string, enabled: boolean) {
  return useQuery({ queryKey: getChannelMembersKey(teamId), queryFn: () => getChannelMembers(teamId), enabled, retry: false, gcTime: 0 });
}

/** The ticked people onto the team together; like any membership change it refreshes the lists, counts and audit. */
export function useAddMembers(teamId: string) {
  const refresh = useRefreshTeams();
  return useMutation({ mutationFn: (v: { personIds: string[]; reason: string }) => addMembers({ teamId, ...v }), onSuccess: refresh });
}

export function useRemoveMember(teamId: string) {
  const refresh = useRefreshTeams();
  return useMutation({ mutationFn: (v: { personId: string; reason: string }) => removeMember({ teamId, ...v }), onSuccess: refresh });
}
