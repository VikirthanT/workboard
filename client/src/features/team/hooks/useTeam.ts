import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ADMINS_KEY, AUDIT_KEY, BOARD_KEY, ME_KEY, TEAMS_KEY, UNASSIGNED_KEY, getTeamMembersKey, getUnassignedKey } from '../../../app/constants/queryKeys';
import { addMember, getTeamMembers, removeMember, searchUnassignedPeople } from '../../../services/api';

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

export function useRemoveMember(teamId: string) {
  const refresh = useRefreshTeams();
  return useMutation({ mutationFn: (v: { personId: string; reason: string }) => removeMember({ teamId, ...v }), onSuccess: refresh });
}
