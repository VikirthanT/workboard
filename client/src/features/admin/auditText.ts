import type { AuditEntry } from '../../app/types/types';

/** A text fact the server stored in the entry's `details`, or `fallback` when it is missing or not text. */
const detail = (e: AuditEntry, key: string, fallback: string): string => {
  const v = e.details?.[key];
  return typeof v === 'string' && v ? v : fallback;
};

/** A plain sentence for one audit entry. A person or team that no longer exists reads as "someone" / "a team". */
export function describeAudit(e: AuditEntry): string {
  const person = e.personName ?? 'someone';
  const team = e.teamName ?? 'a team';
  switch (e.action) {
    case 'team.create': return `Created ${team} with ${person} as manager`;
    case 'team.manager_change': return `Made ${person} the manager of ${team}`;
    case 'team.delete': return `Deleted ${team}`;
    case 'member.add': return `Added ${person} to ${team}`;
    case 'member.remove': return `Removed ${person} from ${team}`;
    case 'admin.grant': return `Made ${person} an admin`;
    case 'admin.revoke': return `Revoked admin from ${person}`;
    case 'auth.login': return 'Signed in'; // the Who column already names the person
    case 'auth.login_failed': return `Sign-in refused for ${detail(e, 'email', 'someone')}`;
    case 'task.delete': {
      const owner = typeof e.details?.assignee === 'string' ? ` (assigned to ${e.details.assignee})` : '';
      return `Deleted the task “${detail(e, 'title', 'a task')}”${owner} from ${team}`;
    }
    case 'task.reassign': return `Reassigned “${detail(e, 'title', 'a task')}” from ${detail(e, 'from', 'nobody')} to ${detail(e, 'to', person)}`;
    default: return e.action; // a newer server action this screen does not know yet: show it as it is
  }
}

const REFUSED_BECAUSE: Record<string, string> = {
  domain_not_allowed: 'Not a company account',
  not_onboarded: 'Not set up as a manager or admin',
};

/** The Reason column: a refused sign-in stores the server's error code, shown as words; a sign-in has no reason to give. */
export function auditReason(e: AuditEntry): string | null {
  if (e.action === 'auth.login') return '–';
  if (e.action === 'auth.login_failed') return REFUSED_BECAUSE[e.reason ?? ''] ?? e.reason;
  return e.reason;
}

/** "1 to 50 of 262", or "No entries" when the log is empty. */
export function pageRange(offset: number, shown: number, total: number): string {
  return shown === 0 ? 'No entries' : `${offset + 1} to ${offset + shown} of ${total}`;
}
