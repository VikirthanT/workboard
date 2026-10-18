import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from '@phosphor-icons/react';
import { cn } from '../../lib/utils';

export const Dialog        = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose   = DialogPrimitive.Close;

interface BaseProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
  children?: React.ReactNode;
}

export function DialogContent({ className, children, ...props }: BaseProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 bg-scrim z-[200] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
      <DialogPrimitive.Content
        className={cn(
          'fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[201] bg-surface rounded-xl border border-line shadow-modal w-[92%] max-w-[520px] max-h-[90vh] flex flex-col overflow-hidden data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
          className
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogHeader({ className, ...props }: BaseProps) {
  return (
    <div
      className={cn('flex items-start justify-between px-5 py-4 border-b border-line shrink-0', className)}
      {...props}
    />
  );
}

export function DialogTitle({ className, ...props }: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      className={cn('text-md font-semibold text-ink', className)}
      {...props}
    />
  );
}

export function DialogDescription({ className, ...props }: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      className={cn('text-xs text-ink-subtle mt-0.5', className)}
      {...props}
    />
  );
}

export function DialogFooter({ className, ...props }: BaseProps) {
  return (
    <div
      className={cn('flex justify-end items-center gap-2.5 px-5 py-[14px] border-t border-line shrink-0', className)}
      {...props}
    />
  );
}

export function DialogBody({ className, ...props }: BaseProps) {
  return (
    <div className={cn('px-5 py-5 overflow-y-auto flex-1 min-h-0', className)} {...props} />
  );
}

export function DialogCloseButton() {
  return (
    <DialogPrimitive.Close className="ml-auto bg-none border-none cursor-pointer text-ink-subtle text-lg leading-none p-1 rounded-sm hover:text-ink hover:bg-surface-subtle transition-colors">
      <X size={16} />
    </DialogPrimitive.Close>
  );
}
