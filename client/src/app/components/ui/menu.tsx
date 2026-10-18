import * as React from 'react';
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { CaretRight } from '@phosphor-icons/react';
import type { Icon } from '@phosphor-icons/react';
import { cn } from '../../lib/utils';

/*
 * The old hand-rolled version of this had: no portal (so it clipped inside any
 * scrolling ancestor), no Escape, no arrow-key navigation, no aria-expanded, and
 * no focus return — keyboard and screen-reader users could not operate it at
 * all. Radix gives all of that, and the rest of this library already builds on
 * Radix for Select, Tabs, Dialog and Checkbox, so consistency argues for it too.
 *
 * The public API is unchanged: trigger, items, align, side, header.
 */

export interface MenuItem {
  label: string;
  icon?: Icon;
  onClick: () => void;
  variant?: 'default' | 'danger';
  disabled?: boolean;
  /** Renders a submenu. `items` is then this item's own menu. */
  items?: MenuItem[];
}

interface MenuProps {
  trigger: React.ReactNode;
  items: MenuItem[];
  /** Radix speaks start/end, not left/right — `align="end"` under an RTL
   *  document is what you actually want, and left/right would pin it wrong. */
  align?: 'start' | 'center' | 'end';
  /** 'bottom' opens downward below the trigger (default); 'top' opens upward,
   *  for triggers pinned near the bottom of the viewport. Radix also flips
   *  automatically on collision, so this is only a preference. */
  side?: 'bottom' | 'top';
  header?: React.ReactNode;
  /** Styles the dropdown panel. */
  className?: string;
  /**
   * Styles the trigger BUTTON, which `className` does not reach — it lands on
   * the panel. Needed whenever the trigger has to fill its container, e.g. a
   * sidebar account card with a control pinned to the far edge. The trigger
   * shrink-wraps to its content by default, so without this a sibling control
   * sits next to the label instead of at the end of the row.
   */
  triggerClassName?: string;
}

const itemClass = (variant: MenuItem['variant'], disabled?: boolean) =>
  cn(
    'flex w-full cursor-pointer items-center gap-2.5 rounded-sm px-3 py-2 text-left text-base font-medium',
    'transition-colors duration-fast outline-none',
    'data-[highlighted]:bg-surface-hover',
    variant === 'danger'
      ? 'text-danger data-[highlighted]:text-danger'
      : 'text-ink-muted data-[highlighted]:text-ink',
    disabled && 'pointer-events-none opacity-45'
  );

export function Menu({
  trigger,
  items,
  align = 'start',
  side = 'bottom',
  header,
  className,
  triggerClassName,
}: MenuProps) {
  return (
    <DropdownMenuPrimitive.Root>
      <DropdownMenuPrimitive.Trigger asChild>
        <button
          type="button"
          /* Radix sets aria-expanded, aria-haspopup and aria-controls on the
             trigger itself. Putting them on a wrapper div is the usual way
             people accidentally lose them. */
          className={cn(
            'cursor-pointer border-none bg-transparent outline-none',
            'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand',
            triggerClassName
          )}
        >
          {trigger}
        </button>
      </DropdownMenuPrimitive.Trigger>

      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
          side={side}
          align={align}
          sideOffset={8}
          collisionPadding={12}
          className={cn(
            'z-50 min-w-[180px] rounded-lg border border-line bg-surface py-1 shadow-overlay',
            'data-[state=open]:animate-scale-in data-[state=closed]:animate-scale-out',
            className
          )}
        >
          {header && (
            <div className="border-b border-line px-3 py-2 text-base text-ink">{header}</div>
          )}

          {items.map((item, i) =>
            item.items ? (
              <DropdownMenuPrimitive.Sub key={`${item.label}-${i}`}>
                <DropdownMenuPrimitive.SubTrigger className={itemClass(item.variant)}>
                  {item.icon && <item.icon size={14} className="shrink-0" />}
                  {item.label}
                  <CaretRight size={12} className="ml-auto shrink-0" />
                </DropdownMenuPrimitive.SubTrigger>
                <DropdownMenuPrimitive.Portal>
                  <DropdownMenuPrimitive.SubContent
                    sideOffset={4}
                    collisionPadding={12}
                    className="z-50 min-w-[160px] rounded-lg border border-line bg-surface py-1 shadow-overlay data-[state=open]:animate-scale-in data-[state=closed]:animate-scale-out"
                  >
                    {item.items.map((child, j) => (
                      <DropdownMenuPrimitive.Item
                        key={`${child.label}-${j}`}
                        disabled={child.disabled}
                        onSelect={child.onClick}
                        className={itemClass(child.variant, child.disabled)}
                      >
                        {child.icon && <child.icon size={14} className="shrink-0" />}
                        {child.label}
                      </DropdownMenuPrimitive.Item>
                    ))}
                  </DropdownMenuPrimitive.SubContent>
                </DropdownMenuPrimitive.Portal>
              </DropdownMenuPrimitive.Sub>
            ) : (
              <DropdownMenuPrimitive.Item
                key={`${item.label}-${i}`}
                disabled={item.disabled}
                /* onSelect, not onClick: Radix fires it on click AND on Enter,
                   and it closes the menu. onClick would leave it open on Enter. */
                onSelect={item.onClick}
                className={itemClass(item.variant, item.disabled)}
              >
                {item.icon && <item.icon size={14} className="shrink-0" />}
                {item.label}
              </DropdownMenuPrimitive.Item>
            )
          )}

        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  );
}
