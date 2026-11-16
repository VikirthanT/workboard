import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { StandupChannelField } from './StandupChannelField';

const h = vi.hoisted(() => ({ channels: {} as Record<string, unknown>, name: {} as Record<string, unknown>, asked: vi.fn() }));
vi.mock('./hooks', () => ({
  useStandupChannels: () => h.channels,
  useChannelName: (id: string, enabled: boolean) => { h.asked(id, enabled); return h.name; },
}));

beforeEach(() => {
  vi.useFakeTimers();
  h.asked.mockReset();
  h.channels = { data: [{ id: 'C0NPI', name: 'standup-npi' }], isError: false };
  h.name = { data: undefined, isError: false, error: null };
});
afterEach(() => vi.useRealTimers());

const settle = () => act(() => void vi.advanceTimersByTime(450));

describe('StandupChannelField', () => {
  it('shows the name of a typed id once typing pauses, and asks only for that id', () => {
    h.channels = { data: [], isError: false }; // the standup app lists nothing, so the id is typed
    h.name = { data: { id: 'C0NEW', name: 'new-standup' }, isError: false, error: null };
    render(<StandupChannelField open value="C0NEW" onChange={vi.fn()} />);

    expect(screen.getByLabelText(/Standup channel/)).toHaveValue('C0NEW');
    expect(screen.queryByText('#new-standup')).not.toBeInTheDocument(); // still within the pause
    settle();
    expect(screen.getByText('#new-standup')).toBeInTheDocument();
    expect(h.asked).toHaveBeenLastCalledWith('C0NEW', true);
  });

  it('says why a typed id cannot be found', () => {
    h.channels = { data: [], isError: false };
    h.name = { data: undefined, isError: true, error: { response: { data: { detail: { message: 'Slack cannot find this channel. Check the channel id.' } } } } };
    render(<StandupChannelField open value="C0NOPE" onChange={vi.fn()} />);

    settle();

    expect(screen.getByRole('alert')).toHaveTextContent('Slack cannot find this channel. Check the channel id.');
  });

  it('does not look anything up while the picker is used', () => {
    render(<StandupChannelField open value="C0NPI" onChange={vi.fn()} />); // a listed channel: the dropdown, which already has the name

    settle();

    expect(screen.queryByText(/Looking up/)).not.toBeInTheDocument();
    expect(h.asked).not.toHaveBeenCalledWith('C0NPI', true);
  });

  it('passes what is typed on', () => {
    h.channels = { data: [], isError: false };
    const onChange = vi.fn();
    render(<StandupChannelField open value="C0OLD" onChange={onChange} />); // not in the list, so the box is shown

    fireEvent.change(screen.getByLabelText(/Standup channel/), { target: { value: 'C0ABC' } });

    expect(onChange).toHaveBeenCalledWith('C0ABC');
  });
});
