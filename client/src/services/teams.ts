import type { PersonRecord, TeamRecord } from '../app/types/types';
import type { WireIdentity, WirePage, WireTeam } from './backendTypes';
import { apiClient } from './axiosInstance';
import { mapPage, mapPerson, mapTeam } from './mappers';

/** Admin: every team. Manager: only their own. */
export async function getTeams(): Promise<TeamRecord[]> {
  const { data } = await apiClient.get<WireTeam[]>('/teams');
  return data.map(mapTeam);
}

/** The people on a team, manager first. An admin can read any team, a manager their own. */
export async function getTeamMembers(teamId: string): Promise<PersonRecord[]> {
  const { data } = await apiClient.get<WireIdentity[]>(`/teams/${teamId}/members`);
  return data.map(mapPerson);
}

/** The team starts with one person, who becomes its manager. */
export async function createTeam(p: { name: string; initialManagerPersonId: string; reason: string }): Promise<TeamRecord> {
  const { data } = await apiClient.post<WireTeam>('/teams', { name: p.name, initial_manager_person_id: p.initialManagerPersonId, reason: p.reason });
  return mapTeam(data);
}

/** Irreversible: the people go back to no team and the team's data is erased. `confirmName` must match the team's name. */
export async function deleteTeam(p: { teamId: string; confirmName: string; reason: string }): Promise<void> {
  await apiClient.delete(`/teams/${p.teamId}`, { data: { confirm_name: p.confirmName, reason: p.reason } });
}

/** The old manager becomes a plain member and stays on the team. */
export async function changeManager(p: { teamId: string; personId: string; reason: string }): Promise<void> {
  await apiClient.patch(`/teams/${p.teamId}/manager`, { person_id: p.personId, reason: p.reason });
}

/** Active directory people on no team, matching `q` (name or email), for the "Add person" picker. One page of up to 50. */
export async function searchUnassignedPeople(q: string): Promise<PersonRecord[]> {
  const { data } = await apiClient.get<WirePage<WireIdentity>>('/people', { params: { unassigned: true, q: q.trim() || undefined, limit: 50 } });
  return mapPage(data, mapPerson).items;
}

/** The reason is optional for a manager adding to their own team, required by the server for nobody else's. */
export async function addMember(p: { teamId: string; personId: string; reason: string }): Promise<void> {
  await apiClient.post(`/teams/${p.teamId}/members`, { person_id: p.personId, reason: p.reason || undefined });
}

/** Frees the person for another team. Their open tasks stay and show as needing a new owner. */
export async function removeMember(p: { teamId: string; personId: string; reason: string }): Promise<void> {
  await apiClient.delete(`/teams/${p.teamId}/members/${p.personId}`, { data: { reason: p.reason || undefined } });
}
