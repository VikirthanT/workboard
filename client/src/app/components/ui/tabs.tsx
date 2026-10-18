import React from 'react';
import * as TabsPrimitive from '@radix-ui/react-tabs';
import { cn } from '../../lib/utils';

export const Tabs        = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

export function TabsList({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn('flex gap-1 bg-surface border border-line rounded-xl p-[5px] w-fit', className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'px-5 py-[9px] rounded-lg text-md font-medium text-ink-subtle cursor-pointer border-none bg-transparent transition-all duration-base outline-none',
        'hover:text-ink hover:bg-surface-subtle',
        'data-[state=active]:bg-brand data-[state=active]:text-ink-inverse data-[state=active]:shadow-raised',
        className
      )}
      {...props}
    />
  );
}

export function FilterTabsList({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn('flex gap-[3px] bg-surface border border-line rounded-lg p-1 w-fit', className)}
      {...props}
    />
  );
}

export function FilterTabsTrigger({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'px-[14px] py-[7px] rounded-sm text-base font-medium text-ink-subtle cursor-pointer border-none bg-transparent transition-all duration-fast outline-none',
        'hover:text-ink hover:bg-surface-subtle',
        'data-[state=active]:bg-ink data-[state=active]:text-ink-inverse',
        className
      )}
      {...props}
    />
  );
}
