import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '../../lib/utils';

/*
 * Buttons sit still — no hover lift, no glow. Feedback is colour on hover
 * plus a 0.98 press scale. `default` is the only accent-filled variant, so
 * a screen with two primaries is a bug you can see.
 *
 * warning / success-outline are quiet washes that deepen on hover rather
 * than flashing solid — a solid amber button is almost never the right call.
 *
 * `focus-ring` is the system-wide focus treatment (outline, not box-shadow,
 * so it survives Windows High Contrast Mode).
 */
export const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap select-none',
    'rounded-md border border-transparent font-sans text-base font-medium',
    'transition-colors duration-fast focus-ring',
    'active:scale-[0.98] disabled:active:scale-100',
    'disabled:opacity-45 disabled:cursor-not-allowed',
  ],
  {
    variants: {
      variant: {
        default:         'bg-brand text-brand-fg hover:bg-brand-hover',
        outline:         'bg-surface text-ink-muted border-line hover:border-line-strong hover:bg-surface-subtle hover:text-ink',
        ghost:           'bg-transparent text-ink-muted hover:bg-surface-hover hover:text-ink',
        destructive:     'bg-danger text-danger-fg hover:bg-danger-hover',
        warning:         'bg-warning-subtle text-warning-ink border-warning-border hover:bg-warning hover:text-warning-fg hover:border-warning',
        'success-outline': 'bg-success-subtle text-success-ink border-success-border hover:bg-success hover:text-success-fg hover:border-success',
      },
      size: {
        /* `lg` is a size, not a layout — `w-full` belongs on the caller's
           className, otherwise a size variant silently re-lays-out the page. */
        default: 'h-9 px-4',
        sm:      'h-8 px-3 text-sm',
        lg:      'h-11 px-5 text-md',
        /* `icon` must not set a background or colour, or `icon` + `outline`
           (the common toolbar case) renders as a ghost button. */
        icon:    'size-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render the child element instead of a <button> (Radix `asChild`).
   *  Requires a ref-capable child. */
  asChild?: boolean;
}

/* forwardRef is not optional: without it every consumer that needs a ref —
   Tooltip, Popover, Radix trigger, menu anchoring — hits a wall. */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        /* A <button> inside a <form> defaults to submit. That has caused
           real bugs; make the safe choice the default. */
        type={asChild ? type : (type ?? 'button')}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';
