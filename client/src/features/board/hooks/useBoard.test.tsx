import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { BoardQuery } from '../../../app/types/types';
import { getBoard } from '../../../services/api';
import { useBoard } from './useBoard';

vi.mock('../../../services/api', () => ({ getBoard: vi.fn(), getTask: vi.fn(), searchPeople: vi.fn() }));

const query: BoardQuery = { teamId: null, attention: false, personId: null, filters: [], search: '' };
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
);

// A new object each time, as the server's reply is: only its content is the same.
const sameBoard = async () => ({ team: { id: 't1', name: 'NPI' }, tasks: [{ id: 'a', title: 'Wire harness' }], columnTotals: { todo: 1 } }) as never;

beforeEach(() => vi.mocked(getBoard).mockReset());

describe('useBoard polling', () => {
  it('keeps the very same board, and draws nothing again, when a poll finds nothing changed', async () => {
    vi.mocked(getBoard).mockImplementation(sameBoard);
    let renders = 0;
    const { result } = renderHook(() => { renders += 1; return useBoard(query, {}); }, { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    const first = result.current.data;
    const drawn = renders;

    await act(async () => { await result.current.refetch(); });

    expect(getBoard).toHaveBeenCalledTimes(2);
    expect(result.current.data).toBe(first);
    expect(renders).toBe(drawn);
  });

  it('shows the new board when a poll finds a change', async () => {
    vi.mocked(getBoard).mockImplementationOnce(sameBoard).mockImplementation(async () => ({ team: { id: 't1', name: 'NPI' }, tasks: [], columnTotals: { todo: 0 } }) as never);
    const { result } = renderHook(() => useBoard(query, {}), { wrapper });
    await waitFor(() => expect(result.current.data?.tasks).toHaveLength(1));

    await act(async () => { await result.current.refetch(); });

    await waitFor(() => expect(result.current.data?.tasks).toHaveLength(0));
  });
});
