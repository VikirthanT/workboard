import { describe, expect, it } from 'vitest';
import type { PersonRecord } from '../../app/types/types';
import { filterMembers } from './memberFilter';

const person = (name: string, extra: Partial<PersonRecord> = {}): PersonRecord => ({
  id: name, displayName: name, email: `${name.toLowerCase()}@x.test`, slackUserId: `U-${name}`, teamId: 't', teamName: 'NPI',
  active: true, role: 'member', isAdmin: false, ...extra,
});
const asha = person('Asha', { role: 'manager', isAdmin: true });
const ravi = person('Ravi');
const zoe = person('Zoe', { active: false });
const all = [asha, ravi, zoe];

describe('filterMembers', () => {
  it('returns everyone for an empty search and all roles', () => expect(filterMembers(all, '', 'all')).toEqual(all));
  it('treats a blank search as empty', () => expect(filterMembers(all, '   ', 'all')).toEqual(all));
  it('matches name, email and Slack id, ignoring case and spaces', () => {
    expect(filterMembers(all, '  RAVI ', 'all')).toEqual([ravi]);
    expect(filterMembers(all, 'asha@x', 'all')).toEqual([asha]);
    expect(filterMembers(all, 'u-zoe', 'all')).toEqual([zoe]);
  });
  it('returns nothing when no one matches', () => expect(filterMembers(all, 'nobody', 'all')).toEqual([]));
  it('filters by team role', () => {
    expect(filterMembers(all, '', 'manager')).toEqual([asha]);
    expect(filterMembers(all, '', 'member')).toEqual([ravi, zoe]);
  });
  it('filters admins by the admin flag, so an admin manager is in both lists', () => {
    expect(filterMembers(all, '', 'admin')).toEqual([asha]);
    expect(filterMembers(all, '', 'manager')).toContain(asha);
  });
  it('combines the search and the role filter', () => {
    expect(filterMembers(all, 'ravi', 'manager')).toEqual([]);
    expect(filterMembers(all, 'ravi', 'member')).toEqual([ravi]);
  });
  it('does not match regex characters literally as patterns', () => expect(filterMembers(all, '.*', 'all')).toEqual([]));
  it('handles an empty team', () => expect(filterMembers([], 'a', 'all')).toEqual([]));
});
