import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ChannelMember } from '../../app/types/types';
import { person } from '../../test/fixtures';
import { PullFromSlackDialog } from './PullFromSlackDialog';

const h = vi.hoisted(() => ({ found: {} as Record<string, unknown>, add: vi.fn() }));
vi.mock('./hooks', () => ({
  useChannelMembers: () => h.found,
  useAddMembers: () => ({ mutate: h.add, isPending: false }),
}));

const member = (name: string, state: ChannelMember['state'], teamName: string | null = null): ChannelMember => ({
  person: person({ id: name, displayName: name, email: `${name.toLowerCase()}@example.test` }), state, teamName,
});
const loaded = (members: ChannelMember[], notInDirectory = 0) => ({ data: { channelId: 'C0NPI', members, notInDirectory }, isPending: false, isError: false, error: null });
const npi = { id: 't1', name: 'NPI' };

beforeEach(() => h.add.mockReset());

describe('PullFromSlackDialog', () => {
  it('ticks the people who can join and says why the others cannot', () => {
    h.found = loaded([member('Meena', 'available'), member('Ravi', 'on_this_team'), member('Zoe', 'on_other_team', 'QA'), member('Omar', 'unavailable')], 2);
    render(<PullFromSlackDialog team={npi} reasonOptional onClose={vi.fn()} />);

    expect(screen.getByRole('checkbox', { name: /Meena/ })).toBeChecked();
    for (const name of [/Ravi/, /Zoe/, /Omar/]) expect(screen.getByRole('checkbox', { name })).toBeDisabled();
    expect(screen.getByText('Already on this team')).toBeInTheDocument();
    expect(screen.getByText('On QA')).toBeInTheDocument();
    expect(screen.getByText(/Cannot be added/)).toBeInTheDocument();
    expect(screen.getByText(/1 can join · 3 cannot · 2 not in the directory/)).toBeInTheDocument();
  });

  it('adds only the ticked people, together, and tells the page how many', async () => {
    h.found = loaded([member('Meena', 'available'), member('Asha', 'available')]);
    h.add.mockImplementation((_v, o) => o?.onSuccess?.());
    const onClose = vi.fn();
    render(<PullFromSlackDialog team={npi} reasonOptional onClose={onClose} />);

    await userEvent.click(screen.getByRole('checkbox', { name: /Asha/ })); // untick one
    await userEvent.click(screen.getByRole('button', { name: 'Add 1 person' }));

    expect(h.add).toHaveBeenCalledTimes(1);
    expect(h.add.mock.calls[0][0]).toMatchObject({ personIds: ['Meena'] });
    expect(onClose).toHaveBeenCalledWith(1);
  });

  it('adds nobody when nobody is ticked', async () => {
    h.found = loaded([member('Meena', 'available')]);
    render(<PullFromSlackDialog team={npi} reasonOptional onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole('button', { name: 'Untick all' }));
    await userEvent.click(screen.getByRole('button', { name: 'Add 0 people' }));

    expect(h.add).not.toHaveBeenCalled();
    expect(screen.getByText('Tick at least one person to add.')).toBeInTheDocument();
  });

  it('says what is wrong, in the server’s words, when the channel is not set or cannot be read, and cannot add', () => {
    h.found = { data: undefined, isPending: false, isError: true, error: { response: { data: { detail: { message: 'Slack cannot find this channel. Check the channel id.' } } } } };
    render(<PullFromSlackDialog team={npi} reasonOptional onClose={vi.fn()} />);

    expect(screen.getByText('The channel could not be read')).toBeInTheDocument();
    expect(screen.getByText('Slack cannot find this channel. Check the channel id.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Add / })).toBeDisabled();
  });

  it('shows the server’s message when the add is refused', async () => {
    h.found = loaded([member('Meena', 'available')]);
    h.add.mockImplementation((_v, o) => o?.onError?.({ response: { data: { detail: { message: 'Meena is already on a team.' } } } }));
    render(<PullFromSlackDialog team={npi} reasonOptional onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole('button', { name: 'Add 1 person' }));

    expect(screen.getByText('Meena is already on a team.')).toBeInTheDocument();
  });

  it('shows a big channel a page of 25 at a time, and keeps the ticks across pages', async () => {
    const people = Array.from({ length: 60 }, (_, n) => member(`Person${String(n).padStart(2, '0')}`, 'available'));
    h.found = loaded(people);
    h.add.mockImplementation((_v, o) => o?.onSuccess?.());
    const onClose = vi.fn();
    render(<PullFromSlackDialog team={npi} reasonOptional onClose={onClose} />);

    expect(screen.getAllByRole('checkbox')).toHaveLength(25);
    expect(screen.getByText('1 to 25 of 60')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();

    await userEvent.click(screen.getByRole('checkbox', { name: /Person00/ })); // untick one on page 1
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('26 to 50 of 60')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Person25/ })).toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('51 to 60 of 60')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: 'Add 59 people' })); // all but the one unticked, from every page
    expect(h.add.mock.calls[0][0].personIds).toHaveLength(59);
    expect(h.add.mock.calls[0][0].personIds).not.toContain('Person00');
    expect(onClose).toHaveBeenCalledWith(59);
  });

  it('shows no paging for a small channel', () => {
    h.found = loaded([member('Meena', 'available')]);
    render(<PullFromSlackDialog team={npi} reasonOptional onClose={vi.fn()} />);

    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument();
  });

  it('waits for the reason from an admin', () => {
    h.found = loaded([member('Meena', 'available')]);
    render(<PullFromSlackDialog team={npi} onClose={vi.fn()} />);

    expect(screen.getByRole('button', { name: 'Add 1 person' })).toBeDisabled(); // no reason typed yet
  });
});
