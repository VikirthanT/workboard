import { toISODate } from '../../app/domain/dates';
import { formatDayWithWeekday } from '../../app/lib/format';
import type { StandupPost } from '../../app/types/types';

/**
 * "Posted Wed 11 Nov": the day the person actually posted (shown in the viewer's own time zone), not the Monday of the
 * standup's week, so a late reply reads as late. Falls back to the standup's date when the standup app gave no time.
 */
export function postedLabel(post: StandupPost): string {
  const day = post.postedAt ? toISODate(new Date(post.postedAt)) : post.date;
  return `Posted ${formatDayWithWeekday(day)}`;
}

/** True when they wrote something under Blockers. */
export function hasBlocker(post: StandupPost | null): boolean {
  return !!post?.blockers?.trim();
}
