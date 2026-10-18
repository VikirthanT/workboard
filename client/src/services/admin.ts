import type { AuditEntry, Page, PersonRecord } from '../app/types/types';
import type { WireAudit, WireIdentity, WirePage } from './backendTypes';
import { apiClient } from './axiosInstance';
import { mapAudit, mapPage, mapPerson } from './mappers';

/** Make or revoke admin. The server refuses a no-op and the last active admin. */
export async function setAdmin(p: { personId: string; isAdmin: boolean; reason: string }): Promise<void> {
  await apiClient.patch(`/people/${p.personId}/admin`, { is_admin: p.isAdmin, reason: p.reason });
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
