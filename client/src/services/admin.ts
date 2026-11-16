import type { AuditEntry, DirectorySyncResult, Page, PersonRecord } from '../app/types/types';
import type { WireAudit, WireDirectorySync, WireIdentity, WirePage } from './backendTypes';
import { apiClient } from './axiosInstance';
import { mapAudit, mapPage, mapPerson } from './mappers';

/** Make or revoke admin. The server refuses a no-op and the last active admin. */
export async function setAdmin(p: { personId: string; isAdmin: boolean; reason: string }): Promise<void> {
  await apiClient.patch(`/people/${p.personId}/admin`, { is_admin: p.isAdmin, reason: p.reason });
}

/**
 * Refresh the people directory from the Slack workspace now (admins only): the run the server makes every week. People in
 * Slack are added or refreshed, people who left are made inactive (never deleted), and the run is audited under the
 * admin's name. The server refuses a run that would deactivate a large share of people (it says how to force it).
 */
export async function syncPeople(): Promise<DirectorySyncResult> {
  const { data } = await apiClient.post<WireDirectorySync>('/people/sync');
  return {
    people: data.people, added: data.added, reactivated: data.reactivated, deactivated: data.deactivated,
    deactivatedOnATeam: data.deactivated_on_a_team, newAdmins: data.new_admins, skipped: data.skipped,
  };
}

/** Everyone with admin access, on a team or not (an admin may be only an admin). Up to 200, far more than there will be. */
export async function getAdmins(): Promise<PersonRecord[]> {
  const { data } = await apiClient.get<WirePage<WireIdentity>>('/people', { params: { admins: true, limit: 200 } });
  return mapPage(data, mapPerson).items;
}

/** Active directory people matching `q` (name or email), whoever they are, for the "Add admin" picker. One page of up to 50. */
export async function searchPeople(q: string): Promise<PersonRecord[]> {
  const { data } = await apiClient.get<WirePage<WireIdentity>>('/people', { params: { q: q.trim() || undefined, limit: 50 } });
  return mapPage(data, mapPerson).items;
}

/** One page of the access audit log, newest first (admins only). */
export async function getAudit(p: { limit: number; offset: number }): Promise<Page<AuditEntry>> {
  const { data } = await apiClient.get<WirePage<WireAudit>>('/audit-log', { params: p });
  return mapPage(data, mapAudit);
}
