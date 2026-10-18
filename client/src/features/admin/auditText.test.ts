import { describe, expect, it } from 'vitest';
import type { AuditEntry } from '../../app/types/types';
import { describeAudit, pageRange } from './auditText';

const entry = (action: string, extra: Partial<AuditEntry> = {}): AuditEntry => ({
  id: '1', action, actorName: 'Admin', personName: 'Ravi', teamName: 'NPI', reason: null, details: null, createdAt: '2026-10-17T10:00:00Z', ...extra,
});

describe('describeAudit', () => {
  it.each([
    ['team.create', 'Created NPI with Ravi as manager'],
    ['team.manager_change', 'Made Ravi the manager of NPI'],
    ['team.delete', 'Deleted NPI'],
    ['member.add', 'Added Ravi to NPI'],
    ['member.remove', 'Removed Ravi from NPI'],
    ['admin.grant', 'Made Ravi an admin'],
    ['admin.revoke', 'Revoked admin from Ravi'],
  ])('%s reads as a sentence', (action, text) => expect(describeAudit(entry(action))).toBe(text));

  it('says "someone" or "a team" when the person or team is gone', () => {
    expect(describeAudit(entry('member.add', { personName: null, teamName: null }))).toBe('Added someone to a team');
  });
  it('names a deleted task and who it was assigned to', () => {
    const e = entry('task.delete', { details: { title: 'Wire harness', assignee: 'Ravi' } });
    expect(describeAudit(e)).toBe('Deleted the task “Wire harness” (assigned to Ravi) from NPI');
  });
  it('still reads when a deleted task has no assignee or title recorded', () => {
    expect(describeAudit(entry('task.delete', { details: null }))).toBe('Deleted the task “a task” from NPI');
    expect(describeAudit(entry('task.delete', { details: { title: 7, assignee: null } }))).toBe('Deleted the task “a task” from NPI');
  });
  it('says who a task moved from and to', () => {
    const e = entry('task.reassign', { details: { title: 'Wire harness', from: 'Ravi', to: 'Asha' } });
    expect(describeAudit(e)).toBe('Reassigned “Wire harness” from Ravi to Asha');
  });
  it('copes with a reassignment whose details are missing', () => {
    expect(describeAudit(entry('task.reassign', { details: null }))).toBe('Reassigned “a task” from nobody to Ravi');
  });
  it('shows an action it does not know as it is', () => expect(describeAudit(entry('team.rename'))).toBe('team.rename'));
});

describe('pageRange', () => {
  it('describes a middle page', () => expect(pageRange(50, 50, 262)).toBe('51 to 100 of 262'));
  it('describes a short last page', () => expect(pageRange(250, 12, 262)).toBe('251 to 262 of 262'));
  it('says so when there are no entries', () => expect(pageRange(0, 0, 0)).toBe('No entries'));
  it('says so when the offset is past the end', () => expect(pageRange(500, 0, 262)).toBe('No entries'));
});
