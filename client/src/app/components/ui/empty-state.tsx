import React from 'react';
import type { Icon } from '@phosphor-icons/react';
import { cn } from '../../lib/utils';

interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Phosphor icon. Typed from the library so its props stay in sync. */
  icon?: Icon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ className, icon: Icon, title, description, action, ...props }: EmptyStateProps) {
  return (
    <div
      className={cn('flex flex-col items-center justify-center text-center gap-3 px-6 py-16', className)}
      {...props}
    >
      {Icon && (
        /* aria-hidden: the glyph repeats the title, so exposing it just adds an
           unlabelled graphic to the accessibility tree. The wrapper is the
           hidden element rather than the Icon itself, because Icon is a caller
           component and we do not control what it renders. */
        <div
          aria-hidden
          className="w-12 h-12 rounded-full flex items-center justify-center bg-surface-subtle text-ink-subtle"
        >
          <Icon size={20} />
        </div>
      )}
      <div>
        <div className="text-md font-semibold text-ink">{title}</div>
        {description && <p className="text-base text-ink-subtle mt-1 max-w-[38ch]">{description}</p>}
      </div>
      {action}
    </div>
  );
}
