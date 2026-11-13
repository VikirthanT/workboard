import { describe, expect, it } from 'vitest';
import type { StandupPost } from '../../app/types/types';
import { hasBlocker, postedLabel } from './standupStatus';

const post = (over: Partial<StandupPost> = {}): StandupPost => ({
  date: '2026-11-09', postedAt: null, lateReply: false, lastWeek: '- a', thisWeek: '- b', blockers: null, message: null, ...over,
});

describe('postedLabel', () => {
  it('shows the day they actually posted, not the standup week\'s Monday', () => {
    // Midday UTC, so the calendar day is the same in every time zone from UTC-11 to UTC+11.
    expect(postedLabel(post({ postedAt: '2026-11-11T12:00:00Z' }))).toBe('Posted Wed 11 Nov');
  });

  it('falls back to the standup date when the standup app gave no time', () => {
    expect(postedLabel(post())).toBe('Posted Mon 9 Nov');
  });
});

describe('hasBlocker', () => {
  it('is true only when something is written under Blockers', () => {
    expect(hasBlocker(post({ blockers: '- waiting on parts' }))).toBe(true);
    expect(hasBlocker(post({ blockers: '   ' }))).toBe(false);
    expect(hasBlocker(post({ blockers: null }))).toBe(false);
    expect(hasBlocker(null)).toBe(false);
  });
});
