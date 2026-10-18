/* Local-date helpers. Due dates are plain calendar days (YYYY-MM-DD), so they
   are compared as strings/day numbers and never pass through a timezone. */

const pad = (n: number) => String(n).padStart(2, '0');

export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function todayISO(now: Date = new Date()): string {
  return toISODate(now);
}

export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  return toISODate(new Date(y, m - 1, d + days));
}

/** Whole days from `from` to `to` (positive when `to` is later). */
export function diffDays(from: string, to: string): number {
  const [fy, fm, fd] = from.split('-').map(Number);
  const [ty, tm, td] = to.split('-').map(Number);
  return Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(fy, fm - 1, fd)) / 86_400_000);
}

export interface DateRange { from: string; to: string }

/** Monday to Sunday containing `today`. */
export function weekRange(today: string): DateRange {
  const [y, m, d] = today.split('-').map(Number);
  const back = (new Date(y, m - 1, d).getDay() + 6) % 7;
  const from = addDays(today, -back);
  return { from, to: addDays(from, 6) };
}

export function monthRange(today: string): DateRange {
  const [y, m] = today.split('-').map(Number);
  return { from: toISODate(new Date(y, m - 1, 1)), to: toISODate(new Date(y, m, 0)) };
}

/** Calendar quarter (Jan-Mar, Apr-Jun, ...). */
export function quarterRange(today: string): DateRange {
  const [y, m] = today.split('-').map(Number);
  const q = Math.floor((m - 1) / 3) * 3;
  return { from: toISODate(new Date(y, q, 1)), to: toISODate(new Date(y, q + 3, 0)) };
}
