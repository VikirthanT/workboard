import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TeamSection } from './TeamSection';
import { person, team } from '../../test/fixtures';

const boss = person({ id: 'm', displayName: 'Boss One', role: 'manager' });
const ann = person({ id: 'a', displayName: 'Ann Member' });

function setup(props: Partial<React.ComponentProps<typeof TeamSection>> = {}) {
  const fns = { onAdd: vi.fn(), onRemove: vi.fn() };
  render(<TeamSection team={team()} members={[boss, ann]} totalMembers={2} {...fns} {...props} />);
  return fns;
}

describe('TeamSection', () => {
  it('collapses and expands from the header', async () => {
    setup();
    expect(screen.getByText('Ann Member')).toBeInTheDocument();
    const toggle = screen.getByRole('button', { name: /Alpha/ });
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('Ann Member')).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.getByText('Ann Member')).toBeInTheDocument();
  });

  it('starts folded when defaultOpen is false', () => {
    setup({ defaultOpen: false });
    expect(screen.queryByText('Ann Member')).not.toBeInTheDocument();
  });

  it('says the team is empty only when it has no one at all', () => {
    setup({ members: [], totalMembers: 0 });
    expect(screen.getByText('No one on this team yet.')).toBeInTheDocument();
  });

  it('says nothing matches when a filter hides everyone, and shows "x of y"', () => {
    setup({ members: [], totalMembers: 2 });
    expect(screen.getByText('No one here matches.')).toBeInTheDocument();
    expect(screen.getByText('0 of 2')).toBeInTheDocument();
  });

  it('shows the standup channel button only when the caller can edit it, and opens the editor', async () => {
    const { rerender } = render(<TeamSection team={team({ standupChannelId: 'C0NPI' })} members={[boss]} totalMembers={1} onAdd={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /Standup channel of/ })).not.toBeInTheDocument();

    const onEditChannel = vi.fn();
    rerender(<TeamSection team={team({ standupChannelId: 'C0NPI' })} members={[boss]} totalMembers={1} onAdd={vi.fn()} onRemove={vi.fn()} onEditChannel={onEditChannel} channelName="npi-standup" />);
    await userEvent.click(screen.getByRole('button', { name: 'Standup channel of Alpha' }));
    expect(screen.getByText('npi-standup')).toBeInTheDocument();
    expect(onEditChannel).toHaveBeenCalledTimes(1);
  });

  it('offers Pull from Slack only to a caller who may, and disables it until the team has a standup channel', async () => {
    const { rerender } = render(<TeamSection team={team({ standupChannelId: 'C0NPI' })} members={[boss]} totalMembers={1} onAdd={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /Pull from Slack/ })).not.toBeInTheDocument();

    const onPullFromSlack = vi.fn();
    rerender(<TeamSection team={team({ standupChannelId: null })} members={[boss]} totalMembers={1} onAdd={vi.fn()} onRemove={vi.fn()} onPullFromSlack={onPullFromSlack} />);
    expect(screen.getByRole('button', { name: /Pull from Slack/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Pull from Slack/ })).toHaveAttribute('title', 'Set the team’s standup channel first');

    rerender(<TeamSection team={team({ standupChannelId: 'C0NPI' })} members={[boss]} totalMembers={1} onAdd={vi.fn()} onRemove={vi.fn()} onPullFromSlack={onPullFromSlack} />);
    await userEvent.click(screen.getByRole('button', { name: /Pull from Slack/ }));
    expect(onPullFromSlack).toHaveBeenCalledTimes(1);
  });

  it('locks the manager row: remove is disabled and explains why', () => {
    setup();
    expect(screen.getByRole('button', { name: /Boss One is the manager/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Remove Ann Member from the team' })).toBeEnabled();
  });

  it('calls onRemove for a member and onAdd from the header', async () => {
    const { onAdd, onRemove } = setup();
    await userEvent.click(screen.getByRole('button', { name: 'Remove Ann Member from the team' }));
    expect(onRemove).toHaveBeenCalledWith(ann);
    await userEvent.click(screen.getByRole('button', { name: /Add person/ }));
    expect(onAdd).toHaveBeenCalled();
  });

  it('shows Delete team and the Admin tick only when the handlers are given', async () => {
    setup();
    expect(screen.queryByRole('button', { name: /Delete team/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('Admin tick calls its handler with the new value', async () => {
    const onToggleAdmin = vi.fn();
    setup({ onToggleAdmin });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Admin access for Ann Member' }));
    expect(onToggleAdmin).toHaveBeenCalledWith(ann, true);
  });

  it('Delete team calls its handler', async () => {
    const onDeleteTeam = vi.fn();
    setup({ onDeleteTeam });
    await userEvent.click(screen.getByRole('button', { name: 'Delete team Alpha' }));
    expect(onDeleteTeam).toHaveBeenCalled();
  });

  it('the Manager role dropdown is disabled on the manager and offers Manager on a member', async () => {
    const onMakeManager = vi.fn();
    setup({ onMakeManager });
    expect(screen.getByRole('combobox', { name: 'Role of Boss One' })).toBeDisabled();
    await userEvent.click(screen.getByRole('combobox', { name: 'Role of Ann Member' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Manager' }));
    expect(onMakeManager).toHaveBeenCalledWith(ann);
  });

  it('choosing Member on a member does nothing', async () => {
    const onMakeManager = vi.fn();
    setup({ onMakeManager });
    await userEvent.click(screen.getByRole('combobox', { name: 'Role of Ann Member' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Member' }));
    expect(onMakeManager).not.toHaveBeenCalled();
  });
});
