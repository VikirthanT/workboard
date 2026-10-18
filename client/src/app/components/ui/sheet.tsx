import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from '@phosphor-icons/react';
import { cn } from '../../lib/utils';

/*
 * Side panel. AtiUI lists "Drawer" as not built yet, so this is the app's own
 * thin wrapper on the same Radix Dialog + tokens (scrim, shadow-modal, surface).
 * Candidate to upstream into AtiUI.
 */
export const Sheet = DialogPrimitive.Root;
export const SheetTitle = DialogPrimitive.Title;
export const SheetDescription = DialogPrimitive.Description;

export function SheetContent({ className, children, ...props }: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-[200] bg-scrim data-[state=open]:animate-fade-in" />
      <DialogPrimitive.Content
        className={cn(
          'fixed inset-y-0 right-0 z-[201] flex w-full max-w-[520px] flex-col border-l border-line bg-surface shadow-modal outline-none',
          'data-[state=open]:animate-slide-up',
          className,
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function SheetHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex shrink-0 items-start justify-between gap-3 border-b border-line px-5 py-4', className)} {...props}>
      <div className="min-w-0">{children}</div>
      <DialogPrimitive.Close aria-label="Close" className="shrink-0 cursor-pointer rounded-sm border-none bg-transparent p-1 text-ink-subtle transition-colors hover:bg-surface-subtle hover:text-ink focus-ring">
        <X size={16} />
      </DialogPrimitive.Close>
    </div>
  );
}

export const SheetBody = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('min-h-0 flex-1 overflow-y-auto px-5 py-5', className)} {...props} />
);
export const SheetFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex shrink-0 flex-wrap items-center justify-end gap-2.5 border-t border-line px-5 py-3.5', className)} {...props} />
);
