import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';

function getInitials(name?: string, fallback?: string) {
  const source = name?.trim();
  if (source) {
    const parts = source.split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (fallback) return fallback.slice(0, 2).toUpperCase();
  return '?';
}

const avatarVariants = cva(
  'inline-flex items-center justify-center rounded-full text-ink-inverse font-semibold shrink-0 select-none overflow-hidden bg-brand',
  {
    variants: {
      size: {
        sm: 'w-6 h-6 text-xs',
        md: 'w-8 h-8 text-sm',
        lg: 'w-11 h-11 text-base',
      },
    },
    defaultVariants: { size: 'md' },
  }
);

interface AvatarProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, 'color'>,
    VariantProps<typeof avatarVariants> {
  name?: string;
  fallback?: string;
  src?: string;
}

export function Avatar({ className, size, name, fallback, src, ...props }: AvatarProps) {
  return (
    <span className={cn(avatarVariants({ size }), className)} {...props}>
      {src ? (
        <img src={src} alt={name || fallback || ''} className="w-full h-full object-cover" />
      ) : (
        getInitials(name, fallback)
      )}
    </span>
  );
}
