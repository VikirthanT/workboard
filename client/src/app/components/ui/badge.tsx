import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';

/*
 * Badge is a quiet count / tag marker ("3", "New") — not workflow status.
 * For workflow state inside tables, use StatusChip, which is deliberately
 * NOT a pill: dot + plain row text, so tables don't turn into Skittles.
 */
export const badgeVariants = cva(
  'inline-flex items-center justify-center rounded-sm border border-line bg-surface-subtle px-1.5 py-px font-sans text-xs font-semibold leading-[1.5] text-ink-muted tabular-nums whitespace-nowrap',
  {
    variants: {
      tone: {
        neutral: '',
        teal: 'border-brand/30 bg-brand-subtle text-ink',
      },
    },
    defaultVariants: { tone: 'neutral' },
  }
);

interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** @deprecated use `tone="teal"` — kept so old `variant="…"` call sites still compile */
  variant?: string;
  tone?: 'neutral' | 'teal';
}

export function Badge({ className, tone, variant, ...props }: BadgeProps) {
  const resolvedTone = tone ?? (variant === 'teal' || variant === 'revision' || variant === 'approved' ? 'teal' : 'neutral');
  return <span className={cn(badgeVariants({ tone: resolvedTone }), className)} {...props} />;
}
