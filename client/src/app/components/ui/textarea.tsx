import React, { forwardRef } from 'react';
import { cn } from '../../lib/utils';

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(
          'w-full px-3 py-[10px] border-[1.5px] border-line rounded-lg bg-surface text-ink font-sans text-base outline-none transition-[border-color,box-shadow] duration-base resize-vertical min-h-[72px] focus:border-brand focus:bg-surface focus-ring',
          className
        )}
        {...props}
      />
    );
  }
);
