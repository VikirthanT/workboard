import type { PersonRecord, TeamRecord } from '../app/types/types';

/** Synthetic people only: real directory rows must never appear in a tracked file. */
export const person = (over: Partial<PersonRecord> = {}): PersonRecord => ({
  id: 'p1',
  displayName: 'Test Person',
  email: 'test.person@example.test',
  slackUserId: 'DEMO-1',
  teamId: 't1',
  active: true,
  teamName: 'Alpha',
  role: 'member',
  isAdmin: false,
  ...over,
});

export const team = (over: Partial<TeamRecord> = {}): TeamRecord => ({ id: 't1', name: 'Alpha', manager: null, memberCount: 0, ...over });
