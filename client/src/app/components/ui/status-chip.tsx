import React from 'react';
import { cn } from '../../lib/utils';

/*
 * Workflow status for table rows and lists: a 6px dot, sentence-case label,
 * soft wash and a hairline inset ring. The dot is the signal — the colour is
 * only there to confirm it. Neutral states (draft / cancelled / stopped /
 * skipped) share one quiet style so only live states carry colour at all.
 */

const STYLES_BY_STATUS: Record<string, { wrap: string; dot: string }> = {
  pending: {
    wrap: 'bg-warning-subtle text-warning-ink ring-warning-border',
    dot: 'bg-warning',
  },
  approved: {
    wrap: 'bg-success-subtle text-success-ink ring-success-border',
    dot: 'bg-success',
  },
  rejected: {
    wrap: 'bg-danger-subtle text-danger-ink ring-danger-border',
    dot: 'bg-danger',
  },
  revision_required: {
    wrap: 'bg-brand-subtle text-brand-ink ring-brand-border',
    dot: 'bg-brand',
  },
  revision: {
    wrap: 'bg-brand-subtle text-brand-ink ring-brand-border',
    dot: 'bg-brand',
  },
  /* Access states. Same three treatments as above on purpose — a live account
     and a live document are both "working", and a suspended one is a stopped
     one. Adding them here rather than at the call site is the point of the
     component: the dot is the signal, so a status that renders as plain text
     at one call site and as a dot at another is worse than no chip. */
  active: {
    wrap: 'bg-success-subtle text-success-ink ring-success-border',
    dot: 'bg-success',
  },
  suspended: {
    wrap: 'bg-danger-subtle text-danger-ink ring-danger-border',
    dot: 'bg-danger',
  },
};

const NEUTRAL = {
  wrap: 'bg-surface-subtle text-ink ring-line',
  dot: 'bg-ink-subtle',
};

function humanize(status: string) {
  return status
    .split('_')
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : w))
    .join(' ');
}

interface StatusChipProps extends Omit<React.HTMLAttributes<HTMLSpanElement>, 'children'> {
  status: string;
}

export function StatusChip({ status, className, ...props }: StatusChipProps) {
  const style = STYLES_BY_STATUS[status] ?? NEUTRAL;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-sm px-2 py-[5px] text-sm font-medium leading-none whitespace-nowrap ring-1 ring-inset',
        style.wrap,
        className
      )}
      {...props}
    >
      <span
        aria-hidden
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          style.dot,
          status === 'pending' && 'animate-pulse-dot'
        )}
      />
      {humanize(status)}
    </span>
  );
}
