import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { STANDUP_CHANNELS_KEY, getSuggestionsKey } from '../../../app/constants/queryKeys';
import { getSuggestions, syncSuggestions } from '../../../services/api';
import { useSuggestions, useSyncSuggestions } from './useSuggestions';

vi.mock('../../../services/api', () => ({
  getSuggestions: vi.fn(),
  syncSuggestions: vi.fn(),
  addSuggestions: vi.fn(),
  editSuggestion: vi.fn(),
  rejectSuggestion: vi.fn(),
  restoreSuggestion: vi.fn(),
}));

const page = (lastSyncedAt: string | null) => ({ people: [], standupChannelId: 'C0NPI', lastSyncedAt, standupProblem: null }) as never;

let client: QueryClient;
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;

beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(getSuggestions).mockReset().mockResolvedValue(page(null));
  vi.mocked(syncSuggestions).mockReset();
});

describe('the suggestions page is cached for the session', () => {
  it('is read once, and opening the page again (even after it was closed) does not read it again', async () => {
    const first = renderHook(() => useSuggestions('t1'), { wrapper });
    await waitFor(() => expect(first.result.current.data).toBeDefined());
    first.unmount(); // the page is closed

    const second = renderHook(() => useSuggestions('t1'), { wrapper });
    await waitFor(() => expect(second.result.current.data).toBeDefined());

    expect(getSuggestions).toHaveBeenCalledTimes(1);
  });

  it('keeps one copy per team', async () => {
    const one = renderHook(() => useSuggestions('t1'), { wrapper });
    await waitFor(() => expect(one.result.current.data).toBeDefined());
    const two = renderHook(() => useSuggestions('t2'), { wrapper });
    await waitFor(() => expect(two.result.current.data).toBeDefined());

    expect(getSuggestions).toHaveBeenCalledTimes(2);
  });

  it('a Sync replaces the page with what it returns and marks the channel list stale, without reading the page again', async () => {
    vi.mocked(syncSuggestions).mockResolvedValue(page('2026-11-17T06:30:00Z'));
    client.setQueryData(STANDUP_CHANNELS_KEY, [{ id: 'C0NPI', name: 'standup-npi' }]);
    const view = renderHook(() => ({ page: useSuggestions('t1'), sync: useSyncSuggestions('t1') }), { wrapper });
    await waitFor(() => expect(view.result.current.page.data).toBeDefined());

    await act(async () => { await view.result.current.sync.mutateAsync(undefined); });

    expect(client.getQueryData(getSuggestionsKey('t1'))).toMatchObject({ lastSyncedAt: '2026-11-17T06:30:00Z' });
    expect(getSuggestions).toHaveBeenCalledTimes(1); // the sync's own answer was used
    expect(client.getQueryState(STANDUP_CHANNELS_KEY)?.isInvalidated).toBe(true); // the picker reads the standup app's channels again
  });
});
