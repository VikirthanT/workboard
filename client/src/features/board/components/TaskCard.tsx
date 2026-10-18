import { forwardRef, type HTMLAttributes } from 'react';
import { ArrowBendUpLeft, Prohibit } from '@phosphor-icons/react';
import { Avatar } from '../../../app/components/ui/avatar';
import { Badge } from '../../../app/components/ui/badge';
import { cn } from '../../../app/lib/utils';
import { formatDue } from '../../../app/lib/format';
import type { Task } from '../../../app/types/types';

interface Props extends HTMLAttributes<HTMLDivElement> {
  task: Task;
  dragging?: boolean;
}

/* Priority is the card's colour: a coloured left edge plus a matching tag. */
const PRIORITY_STYLE: Record<Task['priority'], { edge: string; tag: string; label: string }> = {
  high: { edge: 'border-l-danger', tag: 'border-danger-border bg-danger-subtle text-danger-ink', label: 'High' },
  medium: { edge: 'border-l-warning', tag: 'border-warning-border bg-warning-subtle text-warning-ink', label: 'Medium' },
  low: { edge: 'border-l-brand', tag: 'border-brand-border bg-brand-subtle text-brand-ink', label: 'Low' },
};

/* State is a dot + weight, not a pill. Only neutral tags use Badge. */
function Flag({ tone, children }: { tone: 'danger' | 'warning'; children: React.ReactNode }) {
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs font-semibold', tone === 'danger' ? 'text-danger-ink' : 'text-warning-ink')}>
      <span aria-hidden className={cn('size-1.5 rounded-full', tone === 'danger' ? 'bg-danger' : 'bg-warning')} />
      {children}
    </span>
  );
}

export const TaskCard = forwardRef<HTMLDivElement, Props>(function TaskCard({ task, dragging, className, ...props }, ref) {
  const done = task.status === 'done';
  const reason = task.latestReason;
  return (
    <div
      ref={ref}
      role="button"
      tabIndex={0}
      aria-label={`${task.title}. ${task.status.replace('_', ' ')}`}
      className={cn(
        'flex cursor-pointer flex-col gap-2.5 rounded-lg border border-l-4 border-line bg-surface p-3 text-left shadow-raised transition-colors',
        PRIORITY_STYLE[task.priority].edge,
        'hover:border-y-line-strong hover:border-r-line-strong focus-ring',
        dragging && 'opacity-40',
        done && 'opacity-75',
        className,
      )}
      {...props}
    >
      <p className={cn('line-clamp-2 min-w-0 text-base font-medium text-ink', done && 'line-through decoration-ink-subtle')}>{task.title}</p>

      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <span className={cn('inline-flex items-center rounded-sm border px-1.5 py-px text-xs font-semibold leading-[1.5]', PRIORITY_STYLE[task.priority].tag)}>
          {PRIORITY_STYLE[task.priority].label}<span className="sr-only"> priority</span>
        </span>
        {task.overdue && <Flag tone="danger">Overdue</Flag>}
        {task.dueSoon && <Flag tone="warning">Due soon</Flag>}
        {task.needsReassignment && <Flag tone="warning">Needs reassignment</Flag>}
        {task.returned && (
          <Badge tone="teal" className="gap-1">
            <ArrowBendUpLeft size={10} aria-hidden />
            Returned{task.returnedCount > 1 ? ` ×${task.returnedCount}` : ''}
          </Badge>
        )}
      </div>

      {reason && (reason.kind === 'blocked' || reason.kind === 'sent_back') && (
        <p className="flex gap-1.5 rounded-sm bg-surface-subtle px-2 py-1.5 text-sm text-ink-muted">
          {reason.kind === 'blocked' ? <Prohibit size={12} className="mt-0.5 shrink-0" aria-hidden /> : <ArrowBendUpLeft size={12} className="mt-0.5 shrink-0" aria-hidden />}
          <span className="line-clamp-3">{reason.note}</span>
        </p>
      )}

      <div className="flex items-center justify-between gap-2 text-sm text-ink-subtle">
        <span className="flex min-w-0 items-center gap-1.5">
          <Avatar size="sm" name={task.assignee.displayName} />
          <span className="truncate">{task.assignee.displayName}</span>
        </span>
        <span className={cn('shrink-0 tabular-nums', task.overdue && 'font-semibold text-danger-ink')}>{formatDue(task.dueAt, done)}</span>
      </div>
    </div>
  );
});
