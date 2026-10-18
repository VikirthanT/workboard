import * as React from 'react';
import { Check, Minus } from '@phosphor-icons/react';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import { cn } from '../../lib/utils';

/*
 * Radix renders a <button role="checkbox">, which is NOT a labelable element
 * — so <label><Checkbox/>text</label> silently does nothing when you click the
 * text. Always pair with <Label htmlFor={id}>, or use CheckboxField below.
 */
export const Checkbox = React.forwardRef<
  React.ComponentRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(function Checkbox({ className, ...props }, ref) {
  return (
    <CheckboxPrimitive.Root
      ref={ref}
      className={cn(
        'size-[17px] shrink-0 cursor-pointer rounded-sm border-[1.5px] border-line-strong bg-surface',
        'transition-colors duration-fast focus-ring',
        'data-[state=checked]:border-brand data-[state=checked]:bg-brand',
        'data-[state=indeterminate]:border-brand data-[state=indeterminate]:bg-brand',
        'disabled:cursor-not-allowed disabled:opacity-45',
        className
      )}
      {...props}
    >
      {/* The Indicator mounts for both checked and indeterminate, so the glyph
          has to switch — otherwise indeterminate renders a tick. */}
      <CheckboxPrimitive.Indicator className="flex items-center justify-center text-ink-inverse">
        {props.checked === 'indeterminate' ? <Minus size={12} /> : <Check size={12} />}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
});

export interface CheckboxFieldProps
  extends React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root> {
  label: React.ReactNode;
  description?: React.ReactNode;
  /** Renders the description as an error and switches the box to danger. */
  error?: string;
}

/**
 * Checkbox plus its label and description, correctly associated. Use this
 * rather than hand-rolling a <label> wrapper — the wrapper pattern is the
 * reason checkbox labels have never worked.
 */
export function CheckboxField({
  label,
  description,
  error,
  className,
  id,
  ...props
}: CheckboxFieldProps) {
  const generatedId = React.useId();
  const inputId = id ?? generatedId;
  const describedBy = error
    ? `${inputId}-error`
    : description
      ? `${inputId}-description`
      : undefined;

  return (
    <div className={cn('flex items-start gap-2.5', className)}>
      <Checkbox
        id={inputId}
        aria-describedby={describedBy}
        /* Marked invalid, not just described. aria-describedby alone means the
           error is read when focus lands on the box, but nothing tells assistive
           tech the field is in an invalid state — and an error that appears
           after a failed submit is not read at all unless it is announced. */
        aria-invalid={error ? true : undefined}
        {...props}
      />
      <div className="min-w-0 leading-snug">
        <label htmlFor={inputId} className="cursor-pointer text-base text-ink select-none">
          {label}
        </label>
        {(error || description) && (
          <p
            id={describedBy}
            /* role="alert" on the error only. A description is static help text
               and announcing it on mount would be noise; an error appears in
               response to something the user did and has to be spoken. */
            role={error ? 'alert' : undefined}
            className={cn('mt-0.5 text-sm', error ? 'text-danger-ink' : 'text-ink-subtle')}
          >
            {error ?? description}
          </p>
        )}
      </div>
    </div>
  );
}
