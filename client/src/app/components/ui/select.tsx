import React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';
import { CaretDown, Check, MagnifyingGlass } from '@phosphor-icons/react';
import { cn } from '../../lib/utils';

export const Select = SelectPrimitive.Root;
export const SelectValue = SelectPrimitive.Value;
export const SelectGroup = SelectPrimitive.Group;

export function SelectTrigger({ className, children, ...props }: React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        'flex items-center justify-between gap-2 w-full px-[14px] py-[11px] border-[1.5px] border-line rounded-lg bg-surface text-ink font-sans text-base outline-none transition-[border-color,box-shadow] duration-base cursor-pointer focus:border-brand focus-ring data-[placeholder]:text-ink-subtle min-w-0 [&>span]:line-clamp-1 [&>span]:truncate',
        className
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <CaretDown size={14} className="text-ink-subtle shrink-0" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

export function SelectContent({ className, children, position = "popper", sideOffset = 4, ...props }: React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        className={cn(
          /* z-[300]: above Dialog (200/201) and Sheet, or a Select inside a dialog opens behind its scrim. */
          'z-[300] bg-surface border border-line rounded-lg shadow-overlay overflow-hidden min-w-[var(--radix-select-trigger-width)] w-max max-w-[min(24rem,var(--radix-select-content-available-width))]',
          className
        )}
        position={position}
        sideOffset={sideOffset}
        collisionPadding={12}
        {...props}
        onKeyDownCapture={(e) => {
          // A list with a search box: typing always goes to the box, wherever focus or the mouse is (an option the
          // pointer passed over, or one reached with the arrows). Radix's own type-ahead must not see the key.
          const search = e.currentTarget.querySelector('input');
          if (search && document.activeElement !== search && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
            search.focus({ preventScroll: true });
            e.stopPropagation();
          }
        }}
      >
        <SelectPrimitive.Viewport className="p-1 max-h-[260px] overflow-y-auto">
          {children}
        </SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

interface SelectSearchInputProps extends React.ComponentPropsWithoutRef<'input'> {
  value: string;
  onValueChange: (value: string) => void;
}

export function SelectSearchInput({ value, onValueChange, placeholder = "MagnifyingGlass...", ...props }: SelectSearchInputProps) {
  const ref = React.useRef<HTMLInputElement>(null);
  // Typing starts the moment the list opens. Radix moves focus onto the list as it opens, so take it back a frame later.
  React.useEffect(() => {
    const frame = requestAnimationFrame(() => ref.current?.focus({ preventScroll: true }));
    return () => cancelAnimationFrame(frame);
  }, []);
  return (
    <div className="flex items-center gap-2 px-3 py-2 border-b border-line mb-1 sticky top-0 bg-surface z-10">
      <MagnifyingGlass size={14} className="text-ink-subtle shrink-0" />
      <input
        {...props}
        ref={ref}
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className="w-full text-base text-ink placeholder:text-ink-subtle outline-none bg-transparent"
        onKeyDown={(e) => {
          // Typing must not trigger the list's type-ahead, but the arrow keys, Home / End and Escape belong to the
          // list: ArrowDown moves from this box onto the first option and highlights it.
          if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Escape'].includes(e.key)) e.stopPropagation();
        }}
      />
    </div>
  );
}

export function SelectItem({ className, children, ...props }: React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={cn(
        'flex items-center justify-between gap-3 px-3 py-2 text-sm text-ink rounded-sm cursor-pointer outline-none select-none hover:bg-brand-subtle focus:bg-brand-subtle data-[highlighted]:bg-brand-subtle',
        className
      )}
      {...props}
    >
      <SelectPrimitive.ItemText className="block min-w-0 flex-1 truncate">
        {children}
      </SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator className="shrink-0 ml-auto">
        <Check size={12} className="text-brand" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}
