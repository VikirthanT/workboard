import * as React from 'react';
import { cn } from '../../lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'w-full px-4 py-[13px] border-[1.5px] border-line rounded-lg bg-surface text-ink font-sans text-md outline-none transition-[border-color,box-shadow,background] duration-base placeholder:text-ink-subtle',
          'hover:border-line-strong hover:bg-surface focus:border-brand focus:bg-surface focus-ring',
          'disabled:opacity-60 disabled:bg-surface-sunken disabled:text-ink-subtle disabled:border-line/80 disabled:cursor-not-allowed disabled:hover:border-line/80 disabled:hover:bg-surface/50',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);

Input.displayName = 'Input';
