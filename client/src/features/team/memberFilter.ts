import type { PersonRecord } from '../../app/types/types';

export type RoleFilter = 'all' | 'manager' | 'member' | 'admin';

export const ROLE_FILTER_LABEL: Record<RoleFilter, string> = {
  all: 'All roles',
  manager: 'Managers',
  member: 'Members',
  admin: 'Admins',
};

/**
 * The people matching a search box and a role filter. The search looks in name, email and Slack ID, ignores case and
 * surrounding spaces, and an empty search matches everyone. `admin` matches the admin flag, so an admin who is also
 * a manager appears under both Managers and Admins.
 */
export function filterMembers(members: PersonRecord[], search: string, role: RoleFilter): PersonRecord[] {
  const q = search.trim().toLowerCase();
  return members.filter((p) => {
    if (role === 'admin' ? !p.isAdmin : role !== 'all' && p.role !== role) return false;
    return !q || `${p.displayName} ${p.email} ${p.slackUserId}`.toLowerCase().includes(q);
  });
}
