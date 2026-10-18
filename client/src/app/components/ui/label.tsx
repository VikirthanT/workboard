import React from 'react';
import * as LabelPrimitive from '@radix-ui/react-label';
import { cn } from '../../lib/utils';

/*
 * Sentence case, medium weight. Not uppercase-and-tracked: the all-caps
 * micro-label is the single loudest "AI SaaS" tell there is, and a form full
 * of them reads as a template rather than a product. Hierarchy comes from
 * weight and colour instead.
 */
export function Label({ className, ...props }: React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn('block text-sm font-medium text-ink-muted', className)}
      {...props}
    />
  );
}
