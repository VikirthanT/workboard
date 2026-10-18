/* The numbers themselves are computed on the server (server/tasks/services/report.py); this is how the UI reads them. */

export interface ReportCounts {
  todo: number;
  inProgress: number;
  blocked: number;
  review: number;
  overdue: number;
  /** Tasks created in the range (all of them when there is no range). */
  assigned: number;
  /** Tasks closed in the range (all Done tasks when there is no range). */
  done: number;
  returned: number;
  /** done / assigned, null when nothing was assigned. */
  completionRate: number | null;
  /** Done on or before the due date, among Done tasks that had one. */
  onTimeRate: number | null;
  avgDaysToClose: number | null;
}

export type RateTone = 'good' | 'fair' | 'poor' | 'none';

/** How a Completion / On time rate should read: 80% and up good, 50-79% fair, below 50% poor. */
export function rateTone(rate: number | null): RateTone {
  if (rate === null) return 'none';
  return rate >= 0.8 ? 'good' : rate >= 0.5 ? 'fair' : 'poor';
}
