import React from 'react';
import { Moon, Sun } from '@phosphor-icons/react';
import { cn } from '../../lib/utils';
import { useTheme } from '../../lib/theme';

/**
 * Theme toggle.
 *
 * A single icon button, not a switch. There is no track and no knob because
 * there is nothing to drag: the control is on the account card, where the only
 * job is "change this, get out of the way". A switch implies a persistent
 * setting you set once; this is a press.
 *
 * The icon shows the theme currently on screen — moon when dark, sun when
 * light — rather than the theme you would land on. Showing the target reads as
 * "this is already that", which is the standard way a moon button gets
 * misread. The label says the action, so the two never contradict.
 */
export interface ThemeToggleProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> {
  /** Show the current theme name beside the icon. */
  showLabel?: boolean;
}

export function ThemeToggle({ className, showLabel = false, ...props }: ThemeToggleProps) {
  const { resolvedTheme, toggleTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const label = isDark ? 'Switch to light theme' : 'Switch to dark theme';

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={toggleTheme}
      className={cn(
        'inline-flex shrink-0 items-center gap-2 rounded-md p-1.5',
        'text-ink-muted transition-colors duration-fast',
        'hover:bg-surface-hover hover:text-ink focus-ring',
        className
      )}
      {...props}
    >
      {showLabel && (
        <span aria-hidden className="text-sm">
          {isDark ? 'Dark' : 'Light'}
        </span>
      )}
      {/* weight="fill" so the icon reads at 16px: an outline glyph this small
          next to a 13px label looks like a speck. */}
      {isDark ? (
        <Moon weight="fill" className="size-icon-md" />
      ) : (
        <Sun weight="fill" className="size-icon-md" />
      )}
    </button>
  );
}
