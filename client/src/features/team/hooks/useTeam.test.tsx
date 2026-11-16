import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { searchUnassignedPeople } from '../../../services/api';
import { useRefreshTeams, useUnassignedPeople } from './useTeam';

vi.mock('../../../services/api', () => ({
  addMember: vi.fn(), addMembers: vi.fn(), getChannelMembers: vi.fn(), getTeamMembers: vi.fn(), removeMember: vi.fn(), searchUnassignedPeople: vi.fn(),
}));

const page = { items: [], total: 0, limit: 50, offset: 0 } as never;
let client: QueryClient;
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;

beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(searchUnassignedPeople).mockReset().mockResolvedValue(page);
});

describe('the lists of people are cached for the session', () => {
  it('each search is read once, and opening the picker again (even after closing it) does not read it again', async () => {
    const first = renderHook(() => useUnassignedPeople(true, 'ann'), { wrapper });
    await waitFor(() => expect(first.result.current.data).toBeDefined());
    first.unmount();

    const second = renderHook(() => useUnassignedPeople(true, 'ann'), { wrapper });
    await waitFor(() => expect(second.result.current.data).toBeDefined());
    expect(searchUnassignedPeople).toHaveBeenCalledTimes(1);

    const other = renderHook(() => useUnassignedPeople(true, 'bob'), { wrapper }); // a different search is its own read
    await waitFor(() => expect(other.result.current.data).toBeDefined());
    expect(searchUnassignedPeople).toHaveBeenCalledTimes(2);
  });

  it('a membership change or an admin\'s Sync people refreshes them: the next open reads again', async () => {
    const first = renderHook(() => useUnassignedPeople(true, 'ann'), { wrapper });
    await waitFor(() => expect(first.result.current.data).toBeDefined());
    first.unmount();

    const refresh = renderHook(() => useRefreshTeams(), { wrapper });
    await act(async () => { await refresh.result.current(); });

    const again = renderHook(() => useUnassignedPeople(true, 'ann'), { wrapper });
    await waitFor(() => expect(searchUnassignedPeople).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(again.result.current.data).toBeDefined());
  });
});
