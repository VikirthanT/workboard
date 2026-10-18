import { describe, expect, it } from 'vitest';
import { monthRange, quarterRange, weekRange } from './dates';
import { rateTone } from './report';

/* The report numbers are computed on the server (server/tests/test_task_report.py); the client only shows them. */

describe('range helpers', () => {
  it('week runs Monday to Sunday', () => {
    expect(weekRange('2026-10-14')).toEqual({ from: '2026-10-12', to: '2026-10-18' });
    expect(weekRange('2026-10-18')).toEqual({ from: '2026-10-12', to: '2026-10-18' });
  });
  it('month and quarter', () => {
    expect(monthRange('2026-02-10')).toEqual({ from: '2026-02-01', to: '2026-02-28' });
    expect(quarterRange('2026-10-14')).toEqual({ from: '2026-10-01', to: '2026-12-31' });
  });
});

describe('rateTone', () => {
  it('80% and up good, 50-79% fair, under 50% poor, no data none', () => {
    expect([1, 0.8, 0.79, 0.5, 0.49, 0, null].map(rateTone)).toEqual(['good', 'good', 'fair', 'fair', 'poor', 'poor', 'none']);
  });
});
