import type { PersonSuggestions } from '../../app/types/types';
import { Badge } from '../../app/components/ui/badge';
import { cn } from '../../app/lib/utils';
import { hasBlocker, postedLabel } from './standupStatus';

interface Props {
  people: PersonSuggestions[];
  selectedPersonId: string | undefined;
  /** Ids of the suggestions ticked to add, across everyone, so each row can say how many of theirs are ticked. */
  ticked: ReadonlySet<string>;
  onSelect: (personId: string) => void;
}

/* Late reply and Has a blocker are status chips (a word in a tinted box), not dots. */
function Chip({ tone, children }: { tone: 'warning' | 'danger'; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex w-fit items-center rounded-sm border px-1.5 py-px text-xs font-semibold leading-[1.5]',
        tone === 'warning' ? 'border-warning-border bg-warning-subtle text-warning-ink' : 'border-danger-border bg-danger-subtle text-danger-ink',
      )}
    >
      {children}
    </span>
  );
}

/** The team's people, one row each: name, email, when they posted, chips, and how many suggestions wait. */
export function MemberList({ people, selectedPersonId, ticked, onSelect }: Props) {
  return (
    <nav aria-label="Team members" className="flex flex-col overflow-hidden rounded-lg border border-line bg-surface">
      {people.map(({ person, standup, suggestions }) => {
        const selected = person.id === selectedPersonId;
        const waiting = suggestions.filter((s) => s.state === 'pending').length;
        const tickedHere = suggestions.filter((s) => ticked.has(s.id)).length;
        return (
          <button
            key={person.id}
            type="button"
            aria-current={selected ? 'true' : undefined}
            onClick={() => onSelect(person.id)}
            className={cn(
              'flex w-full cursor-pointer items-start gap-2.5 border-0 border-l-[3px] border-t border-t-line bg-transparent px-3.5 py-3 text-left transition-colors first:border-t-0 hover:bg-surface-hover focus-ring',
              selected ? 'border-l-brand bg-surface-subtle' : 'border-l-transparent',
            )}
          >
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="text-md font-semibold text-ink">{person.displayName}</span>
              <span className="truncate text-xs text-ink-subtle">{person.email}</span>
              <span className={cn('text-xs', standup ? 'text-ink-muted' : 'font-semibold text-warning-ink')}>
                {standup ? postedLabel(standup) : 'No standup this week'}
              </span>
              {(standup?.lateReply || hasBlocker(standup)) && (
                <span className="flex flex-wrap gap-1.5">
                  {standup?.lateReply && <Chip tone="warning">Late reply</Chip>}
                  {hasBlocker(standup) && <Chip tone="danger">Has a blocker</Chip>}
                </span>
              )}
            </span>
            <span className="flex flex-none flex-col items-end gap-1">
              <Badge aria-label={`${waiting} waiting`}>{waiting}</Badge>
              {tickedHere > 0 && <span className="text-xs font-semibold text-brand-ink">{tickedHere} selected</span>}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
