import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { CheckCircle, Info, WarningCircle, XCircle } from '@phosphor-icons/react';
import { cn } from '../../lib/utils';

const alertVariants = cva(
  'flex items-start gap-3 rounded-lg border px-4 py-3 text-base',
  {
    variants: {
      /* There is deliberately no blue. `info` is the brand teal — a fourth
       * hue here is what pushed the old version toward generic Tailwind. */
      variant: {
        info:    'bg-brand-subtle text-brand-ink border-brand-border',
        success: 'bg-success-subtle text-success-ink border-success-border',
        warning: 'bg-warning-subtle text-warning-ink border-warning-border',
        danger:  'bg-danger-subtle text-danger-ink border-danger-border',
      },
    },
    defaultVariants: { variant: 'info' },
  }
);

const ICONS = { info: Info, success: CheckCircle, warning: WarningCircle, danger: XCircle } as const;

interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  title?: string;
}

export function Alert({ className, variant = 'info', title, children, ...props }: AlertProps) {
  const Icon = ICONS[variant ?? 'info'];
  return (
    <div className={cn(alertVariants({ variant }), className)} {...props}>
      <Icon size={16} className="shrink-0 mt-0.5" />
      <div className="min-w-0">
        {title && <div className="font-semibold mb-0.5">{title}</div>}
        <div className="opacity-90">{children}</div>
      </div>
    </div>
  );
}
