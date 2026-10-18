import React, { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CalendarBlank as CalendarIcon, CaretLeft, CaretRight } from "@phosphor-icons/react";
import { cn } from "../../lib/utils";

interface DatePickerProps {
  id?: string;
  value: string; // "YYYY-MM-DD" or ""
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  title?: string;
  minDate?: string; // "YYYY-MM-DD" — dates before this are disabled
  maxDate?: string; // "YYYY-MM-DD" — dates after this are disabled
}

interface Placement {
  top: number;
  left: number;
  side: "top" | "bottom";
}

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

/* The panel is a fixed 256px wide and a known height (header + weekday row +
   six week rows + footer). Measuring it properly would mean a layout pass on
   every scroll event; these constants are cheaper and cannot drift out of sync
   with the CSS because both are declared here. */
const PANEL_WIDTH = 256;
const PANEL_HEIGHT = 344;
const TRIGGER_GAP = 6;
const VIEWPORT_MARGIN = 8;

function parseISO(value: string | undefined): Date | null {
  if (!value) return null;
  const parts = value.split("-").map(Number);
  const [y, m, d] = parts;
  if (!y || !m || !d) return null;
  const date = new Date(y, m - 1, d);
  return isNaN(date.getTime()) ? null : date;
}

function toISO(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function isSameDay(a: Date | null, b: Date | null): boolean {
  if (!a || !b) return false;
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

function startOfWeek(date: Date): Date {
  return addDays(date, -date.getDay());
}

function endOfWeek(date: Date): Date {
  return addDays(date, 6 - date.getDay());
}

function shiftMonth(date: Date, delta: number): Date {
  // Clamp the day so 31 Jan + 1 month lands on 28/29 Feb rather than 3 March.
  const target = new Date(date.getFullYear(), date.getMonth() + delta, 1);
  const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  target.setDate(Math.min(date.getDate(), lastDay));
  return target;
}

function buildMonthGrid(viewDate: Date): { date: Date; inMonth: boolean }[] {
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const gridStart = new Date(year, month, 1 - firstOfMonth.getDay());
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i);
    return { date: d, inMonth: d.getMonth() === month };
  });
}

/**
 * Self-contained popover date picker (no external date libs) — rendered
 * through a portal, positioned from the trigger's own rect, closes on
 * outside click / Escape / scroll-reposition.
 *
 * Flips above the trigger when there isn't room below, and clamps
 * horizontally, so it no longer walks off the bottom of the viewport.
 * Arrow keys / Home / End / PageUp / PageDown drive a roving-tabindex grid.
 */
export function DatePicker({
  id,
  value,
  onChange,
  placeholder = "Select date...",
  className,
  disabled,
  title,
  minDate,
  maxDate,
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<Placement | null>(null);
  const [focusedDate, setFocusedDate] = useState<Date | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const dayRefs = useRef(new Map<string, HTMLButtonElement>());

  const selected = parseISO(value);
  const min = parseISO(minDate);
  const max = parseISO(maxDate);
  // Midnight, like parseISO's dates: with the time of day in it, today would sit after a maxDate of today.
  const today = useMemo(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }, []);
  const [viewDate, setViewDate] = useState(() => selected || today);

  const gridRef = useRef<HTMLDivElement>(null);

  function isOutOfRange(d: Date) {
    if (min && d < min) return true;
    if (max && d > max) return true;
    return false;
  }

  function updateRect() {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();

    /* Flip above when the panel would overflow the bottom AND there is more
       room up there. The old version only ever did `r.bottom + 4`, so a trigger
       near the fold pushed the whole calendar off-screen. */
    const spaceBelow = window.innerHeight - r.bottom;
    const spaceAbove = r.top;
    const side: "top" | "bottom" =
      spaceBelow < PANEL_HEIGHT && spaceAbove > spaceBelow ? "top" : "bottom";

    const top =
      side === "top"
        ? Math.max(VIEWPORT_MARGIN, r.top - PANEL_HEIGHT - TRIGGER_GAP)
        : r.bottom + TRIGGER_GAP;

    /* Clamp horizontally so a trigger near the right edge doesn't push the
       panel past the viewport. */
    const maxLeft = window.innerWidth - PANEL_WIDTH - VIEWPORT_MARGIN;
    const left = Math.min(
      Math.max(VIEWPORT_MARGIN, r.left),
      Math.max(VIEWPORT_MARGIN, maxLeft)
    );

    setRect({ top, left, side });
  }

  function openPicker() {
    if (disabled) return;
    setViewDate(selected || today);
    setFocusedDate(selected || today);
    updateRect();
    setOpen(true);
  }

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        // Return focus to the trigger so keyboard users are not dropped at the
        // top of the document.
        triggerRef.current?.focus();
      }
    }
    const reposition = () => updateRect();
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKey);
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKey);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
  }, [open]);

  /* Roving tabindex: exactly one day is tabbable, and arrow keys move it. The
     effect focuses the new cell, and also runs when the month changes so
     PageUp/PageDown land somewhere real. */
  useEffect(() => {
    if (!open) return;
    const target = focusedDate || selected || today;
    const button = dayRefs.current.get(toISO(target));
    button?.focus();
  }, [open, focusedDate, viewDate, selected, today]);

  function selectDate(d: Date) {
    if (isOutOfRange(d)) return;
    onChange(toISO(d));
    setOpen(false);
    triggerRef.current?.focus();
  }

  function moveFocus(next: Date) {
    if (isOutOfRange(next)) return;
    setFocusedDate(next);
    if (
      next.getMonth() !== viewDate.getMonth() ||
      next.getFullYear() !== viewDate.getFullYear()
    ) {
      setViewDate(new Date(next.getFullYear(), next.getMonth(), 1));
    }
  }

  function handleGridKeyDown(e: React.KeyboardEvent) {
    const base = focusedDate || selected || today;
    switch (e.key) {
      case "ArrowLeft":  e.preventDefault(); moveFocus(addDays(base, -1)); break;
      case "ArrowRight": e.preventDefault(); moveFocus(addDays(base, 1)); break;
      case "ArrowUp":    e.preventDefault(); moveFocus(addDays(base, -7)); break;
      case "ArrowDown":  e.preventDefault(); moveFocus(addDays(base, 7)); break;
      case "Home":       e.preventDefault(); moveFocus(startOfWeek(base)); break;
      case "End":        e.preventDefault(); moveFocus(endOfWeek(base)); break;
      case "PageUp":     e.preventDefault(); moveFocus(shiftMonth(base, -1)); break;
      case "PageDown":   e.preventDefault(); moveFocus(shiftMonth(base, 1)); break;
      case "Enter":
      case " ":
        e.preventDefault();
        selectDate(base);
        break;
    }
  }

  const cells = useMemo(() => buildMonthGrid(viewDate), [viewDate]);
  const monthLabel = viewDate.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const displayLabel = selected
    ? selected.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
    : placeholder;

  const rovingDate = focusedDate || selected || today;

  /* A <label for> pointing at this <button> wins over the button's own content
   * when the accessible name is computed — correctly, since button IS a
   * labelable element. The side effect is that the chosen date, which is the
   * content, is never announced: the control reads as "Target date, button"
   * whether it holds a date or not.

   * A hidden description is the fix that does not need to know the field's
   * label text, which lives outside this component. aria-describedby is not
   * overridden by the label, so the value is spoken after the name and role. */
  const valueDescriptionId = `${id ?? 'date-picker'}-value`;

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        title={title}
        onClick={() => (open ? setOpen(false) : openPicker())}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-describedby={valueDescriptionId}
        className={cn(
          "flex h-9 w-full items-center gap-2 rounded-md border-[1.5px] border-line bg-surface px-3 text-left text-base text-ink outline-none",
          "transition-[border-color,box-shadow,background] duration-base hover:border-line-strong",
          "focus-ring data-[state=open]:border-brand",
          "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-subtle disabled:opacity-60",
          className
        )}
      >
        <CalendarIcon size={14} className="shrink-0 text-ink-subtle" />
        <span className={cn("truncate", !selected && "text-ink-subtle")}>{displayLabel}</span>
      </button>

      {/* The value, said out loud. Hidden visually because the trigger already
          shows it — this exists purely so the name is not the whole story. */}
      <span id={valueDescriptionId} className="sr-only">
        {selected ? `Selected ${displayLabel}` : 'No date selected'}
      </span>

      {open &&
        rect &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            aria-label={`Choose a date. Currently ${monthLabel}`}
            /* pointer-events: an open Radix Dialog turns them off for everything outside it, and this panel is portaled
               to <body>; without this, clicks fall through to the dialog's overlay and just close the picker. */
            style={{ position: "fixed", top: rect.top, left: rect.left, pointerEvents: "auto" }}
            className="z-[300] w-64 origin-top rounded-lg border border-line bg-surface p-3 shadow-overlay data-[side=top]:origin-bottom"
            data-side={rect.side}
          >
            <div className="mb-2 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1))}
                className="cursor-pointer rounded-sm p-1 text-ink-subtle transition-colors hover:bg-surface-hover hover:text-ink"
                aria-label="Previous month"
              >
                <CaretLeft size={16} />
              </button>
              <span aria-live="polite" className="text-base font-medium text-ink">
                {monthLabel}
              </span>
              <button
                type="button"
                onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1))}
                className="cursor-pointer rounded-sm p-1 text-ink-subtle transition-colors hover:bg-surface-hover hover:text-ink"
                aria-label="Next month"
              >
                <CaretRight size={16} />
              </button>
            </div>

            <div role="row" className="mb-1 grid grid-cols-7">
              {WEEKDAYS.map((w) => (
                <span
                  key={w}
                  role="columnheader"
                  aria-label={w}
                  className="py-1 text-center text-xs font-medium text-ink-subtle"
                >
                  {w}
                </span>
              ))}
            </div>

            <div
              ref={gridRef}
              role="grid"
              aria-label={monthLabel}
              onKeyDown={handleGridKeyDown}
              className="grid grid-cols-7 gap-y-1"
            >
              {cells.map(({ date, inMonth }) => {
                const isToday = isSameDay(date, today);
                const isSelected = isSameDay(date, selected);
                const isDisabled = isOutOfRange(date);
                const isRoving = isSameDay(date, rovingDate);

                return (
                  <button
                    key={toISO(date)}
                    ref={(el) => {
                      if (el) dayRefs.current.set(toISO(date), el);
                      else dayRefs.current.delete(toISO(date));
                    }}
                    type="button"
                    role="gridcell"
                    tabIndex={isRoving ? 0 : -1}
                    aria-selected={isSelected}
                    aria-label={date.toLocaleDateString(undefined, {
                      weekday: "long",
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                    disabled={isDisabled}
                    onClick={() => selectDate(date)}
                    onFocus={() => setFocusedDate(date)}
                    className={cn(
                      "mx-auto flex size-8 cursor-pointer items-center justify-center rounded-full text-sm transition-colors",
                      inMonth ? "text-ink" : "text-ink-subtle/50",
                      !isSelected && !isDisabled && "hover:bg-brand-subtle",
                      isToday && !isSelected && "border border-brand-border font-medium",
                      isSelected && "bg-brand font-medium text-brand-fg hover:bg-brand",
                      isDisabled && "cursor-not-allowed opacity-30 hover:bg-transparent"
                    )}
                  >
                    {date.getDate()}
                  </button>
                );
              })}
            </div>

            <div className="mt-2.5 flex items-center justify-between border-t border-line pt-2">
              <button
                type="button"
                onClick={() => selectDate(today)}
                disabled={isOutOfRange(today)}
                className="cursor-pointer border-none bg-transparent text-sm font-medium text-brand transition-colors hover:underline disabled:cursor-not-allowed disabled:text-ink-subtle disabled:no-underline"
              >
                Today
              </button>
              {value && (
                <button
                  type="button"
                  onClick={() => {
                    onChange("");
                    setOpen(false);
                    triggerRef.current?.focus();
                  }}
                  className="cursor-pointer border-none bg-transparent text-sm text-ink-subtle transition-colors hover:text-ink hover:underline"
                >
                  Clear
                </button>
              )}
            </div>
          </div>,
          document.body
        )}
    </>
  );
}
