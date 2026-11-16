import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, Funnel, X } from '@phosphor-icons/react';
import { Badge } from '../../../app/components/ui/badge';
import { Button } from '../../../app/components/ui/button';
import { cn } from '../../../app/lib/utils';
import type { BoardFilter } from '../../../app/types/types';

export const FILTER_LABEL: Record<BoardFilter, string> = {
  needs_review: 'Needs my review',
  overdue: 'Overdue',
  blocked: 'Blocked',
  due_week: 'Due this week',
};

const FILTER_HELP: Record<BoardFilter, string> = {
  needs_review: 'Tasks waiting in Review for you to accept or send back',
  overdue: 'Past the due date and not Done',
  blocked: 'Stuck, with a reason on the card',
  due_week: 'Due in the next 7 days',
};

export const ATTENTION_LABEL = 'Needs attention';
const ATTENTION_HELP = 'Overdue, blocked, waiting in Review, or without an owner';

interface Props {
  options: BoardFilter[];
  selected: BoardFilter[];
  /** Badge counts shown beside an option (e.g. how many tasks need your review). */
  counts?: Partial<Record<BoardFilter, number>>;
  /** "Needs attention" is a filter like the rest, kept apart because the server narrows the board with its own switch. */
  attention?: { checked: boolean; count: number; onChange: (on: boolean) => void };
  onToggle: (f: BoardFilter) => void;
  onClear: () => void;
}

/** One line of the menu: a tick, the name with its count, and a line of help. */
function Option({ checked, label, help, count, onToggle }: { checked: boolean; label: string; help: string; count?: number; onToggle: () => void }) {
  return (
    <DropdownMenu.CheckboxItem
      checked={checked}
      // Keep the menu open so several filters can be ticked in one go.
      onSelect={(e) => { e.preventDefault(); onToggle(); }}
      className="flex cursor-pointer items-start gap-2.5 px-3 py-2 outline-none transition-colors data-[highlighted]:bg-surface-hover"
    >
      <span className={cn('mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-sm border', checked ? 'border-brand bg-brand text-ink-inverse' : 'border-line-strong bg-surface')}>
        <DropdownMenu.ItemIndicator><Check size={12} aria-hidden /></DropdownMenu.ItemIndicator>
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 text-base font-medium text-ink">
          {label}
          {count !== undefined && <Badge tone={count > 0 ? 'teal' : 'neutral'}>{count}</Badge>}
        </span>
        <span className="block text-xs text-ink-subtle">{help}</span>
      </span>
    </DropdownMenu.CheckboxItem>
  );
}

/** A removable chip for something active. */
function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <button
      type="button"
      onClick={onRemove}
      aria-label={`Remove filter ${label}`}
      className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-brand-border bg-brand-subtle px-2.5 py-1.5 text-sm font-medium text-brand-ink transition-colors hover:border-brand focus-ring"
    >
      {label}
      <X size={12} aria-hidden />
    </button>
  );
}

/**
 * One dropdown instead of a row of chips. Pick as many as you like; the menu
 * stays open while you do, and what is active shows as removable chips beside it.
 * "Needs attention" is the first option, with how many tasks it would show.
 */
export function FilterMenu({ options, selected, counts = {}, attention, onToggle, onClear }: Props) {
  const active = selected.length + (attention?.checked ? 1 : 0);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <Button variant="outline" aria-label="Filters">
            <Funnel size={14} aria-hidden />
            Filters
            {active > 0 && <Badge tone="teal">{active}</Badge>}
          </Button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="start"
            sideOffset={8}
            collisionPadding={12}
            className="z-50 w-[300px] rounded-lg border border-line bg-surface py-1 shadow-overlay data-[state=open]:animate-scale-in data-[state=closed]:animate-scale-out"
          >
            {attention && (
              <Option checked={attention.checked} label={ATTENTION_LABEL} help={ATTENTION_HELP} count={attention.count} onToggle={() => attention.onChange(!attention.checked)} />
            )}
            {options.map((f) => (
              <Option key={f} checked={selected.includes(f)} label={FILTER_LABEL[f]} help={FILTER_HELP[f]} count={counts[f]} onToggle={() => onToggle(f)} />
            ))}
            {active > 0 && (
              <>
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
                <DropdownMenu.Item onSelect={onClear} className="cursor-pointer px-3 py-2 text-base text-ink-muted outline-none transition-colors data-[highlighted]:bg-surface-hover data-[highlighted]:text-ink">
                  Clear all filters
                </DropdownMenu.Item>
              </>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      {attention?.checked && <Chip label={ATTENTION_LABEL} onRemove={() => attention.onChange(false)} />}
      {selected.map((f) => <Chip key={f} label={FILTER_LABEL[f]} onRemove={() => onToggle(f)} />)}
    </div>
  );
}
