import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReasonFormDialog } from './ReasonFormDialog';

function setup(props: Partial<React.ComponentProps<typeof ReasonFormDialog>> = {}) {
  const onSubmit = vi.fn();
  const onClose = vi.fn();
  render(<ReasonFormDialog open title="Remove Ann" placeholder="Why?" submitLabel="Remove" busy={false} onSubmit={onSubmit} onClose={onClose} {...props} />);
  return { onSubmit, onClose };
}

describe('ReasonFormDialog', () => {
  it('required: marks the field, keeps the button disabled until filled, then submits the trimmed reason', async () => {
    const { onSubmit } = setup();
    expect(screen.getByText('(required)')).toBeInTheDocument();
    const submit = screen.getByRole('button', { name: 'Remove' });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Reason/), '  left the company ');
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    expect(onSubmit).toHaveBeenCalledWith('left the company', expect.any(Function));
  });

  it('required: whitespace alone does not enable the button', async () => {
    setup();
    await userEvent.type(screen.getByLabelText(/Reason/), '   ');
    expect(screen.getByRole('button', { name: 'Remove' })).toBeDisabled();
  });

  it('optional: the button is enabled and an empty reason is submitted', async () => {
    const { onSubmit } = setup({ reasonOptional: true });
    expect(screen.getByText(/\(optional\)/)).toBeInTheDocument();
    expect(screen.queryByText('(required)')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }));
    expect(onSubmit).toHaveBeenCalledWith('', expect.any(Function));
  });

  it('disables the button while busy', () => {
    setup({ reasonOptional: true, busy: true });
    expect(screen.getByRole('button', { name: 'Remove' })).toBeDisabled();
  });

  it('shows the server message passed to fail', async () => {
    const { onSubmit } = setup({ reasonOptional: true });
    onSubmit.mockImplementation((_r: string, fail: (m: string) => void) => fail('Last admin cannot be removed.'));
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Last admin cannot be removed.');
  });

  it('Cancel calls onClose and nothing is submitted', async () => {
    const { onSubmit, onClose } = setup();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('renders nothing when closed', () => {
    setup({ open: false });
    expect(screen.queryByText('Remove Ann')).not.toBeInTheDocument();
  });
});
