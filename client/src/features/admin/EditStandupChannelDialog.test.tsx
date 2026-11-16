import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { team } from '../../test/fixtures';
import { EditStandupChannelDialog } from './EditStandupChannelDialog';

const h = vi.hoisted(() => ({ save: vi.fn(), toast: vi.fn() }));
vi.mock('./hooks', () => ({ useSetStandupChannel: () => ({ mutate: h.save, isPending: false }) }));
vi.mock('./StandupChannelField', () => ({
  StandupChannelField: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <input aria-label="Channel" value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));
vi.mock('../../app/components/ui/toast', () => ({ useToast: () => ({ toast: h.toast }) }));

const npi = team({ id: 't1', name: 'NPI', standupChannelId: 'C0OLD' });

beforeEach(() => {
  h.save.mockReset();
  h.toast.mockReset();
});

describe('EditStandupChannelDialog', () => {
  it('lets a manager save their own team’s channel without a reason', async () => {
    render(<EditStandupChannelDialog team={npi} reasonOptional onClose={vi.fn()} />);

    const save = screen.getByRole('button', { name: 'Save channel' });
    expect(save).toBeEnabled();
    await userEvent.clear(screen.getByLabelText('Channel'));
    await userEvent.type(screen.getByLabelText('Channel'), 'C0NEW');
    await userEvent.click(save);

    expect(h.save).toHaveBeenCalledTimes(1);
    expect(h.save.mock.calls[0][0]).toMatchObject({ teamId: 't1', standupChannelId: 'C0NEW' });
  });

  it('makes an admin give a reason first', async () => {
    render(<EditStandupChannelDialog team={npi} onClose={vi.fn()} />);

    const save = screen.getByRole('button', { name: 'Save channel' });
    expect(save).toBeDisabled();
    await userEvent.type(screen.getByRole('textbox', { name: /Reason/ }), 'The team moved channels');
    expect(save).toBeEnabled();
  });

  it('refuses the channel the team already has', async () => {
    render(<EditStandupChannelDialog team={npi} reasonOptional onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole('button', { name: 'Save channel' }));

    expect(h.save).not.toHaveBeenCalled();
    expect(screen.getByText('That is already the team’s channel.')).toBeInTheDocument();
  });
});
