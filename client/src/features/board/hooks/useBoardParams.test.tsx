import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { useBoardParams } from './useBoardParams';

const at = (url: string) => ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter>;

beforeEach(() => sessionStorage.clear());

describe('useBoardParams', () => {
  it('starts empty', () => {
    const { result } = renderHook(() => useBoardParams(), { wrapper: at('/') });
    expect(result.current.query).toEqual({ teamId: null, attention: false, personId: null, filters: [] });
    expect(result.current.taskId).toBeNull();
  });

  it('brings the view back after a refresh or a trip to another page', () => {
    const first = renderHook(() => useBoardParams(), { wrapper: at('/') });
    act(() => {
      first.result.current.setAttention(true);
      first.result.current.setPerson('p1');
      first.result.current.openTask('t1');
    });
    first.unmount();
    const again = renderHook(() => useBoardParams(), { wrapper: at('/') });
    expect(again.result.current.query).toMatchObject({ attention: true, personId: 'p1' });
    expect(again.result.current.taskId).toBe('t1');
  });

  it('keeps each team its own view', () => {
    const npi = renderHook(() => useBoardParams('npi-id'), { wrapper: at('/') });
    act(() => npi.result.current.toggleFilter('blocked'));
    const other = renderHook(() => useBoardParams('val-id'), { wrapper: at('/') });
    expect(other.result.current.query.filters).toEqual([]);
    expect(npi.result.current.query.filters).toEqual(['blocked']);
  });

  it('toggles and clears filters', () => {
    const { result } = renderHook(() => useBoardParams(), { wrapper: at('/') });
    act(() => result.current.toggleFilter('overdue'));
    act(() => result.current.toggleFilter('blocked'));
    expect(result.current.query.filters).toEqual(['overdue', 'blocked']);
    act(() => result.current.toggleFilter('overdue'));
    expect(result.current.query.filters).toEqual(['blocked']);
    act(() => result.current.clearFilters());
    expect(result.current.query.filters).toEqual([]);
  });

  it('applies the header link /?filter=needs_review once', () => {
    const { result } = renderHook(() => useBoardParams(), { wrapper: at('/?filter=needs_review') });
    expect(result.current.query.filters).toEqual(['needs_review']);
  });

  it('ignores junk in storage and unknown filters', () => {
    sessionStorage.setItem('wb_board:own', '{"filters":["nope","overdue"]}');
    expect(renderHook(() => useBoardParams(), { wrapper: at('/') }).result.current.query.filters).toEqual(['overdue']);
    sessionStorage.setItem('wb_board:own', 'not json');
    expect(renderHook(() => useBoardParams(), { wrapper: at('/') }).result.current.query.filters).toEqual([]);
  });
});
