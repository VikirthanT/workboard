import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DatePicker } from './date-picker';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './dialog';

const day = (n: number) => screen.getAllByRole('gridcell').find((c) => c.textContent === String(n) && !c.className.includes('text-ink-subtle/50'))!;

describe('DatePicker', () => {
  it('a click on a day inside a modal dialog sets the value (the panel is portaled out of the dialog)', async () => {
    const onChange = vi.fn();
    render(
      <Dialog open>
        <DialogContent>
          <DialogTitle>t</DialogTitle><DialogDescription>d</DialogDescription>
          <DatePicker id="due" value="2026-10-15" onChange={onChange} />
        </DialogContent>
      </Dialog>,
    );
    await userEvent.click(screen.getByRole('button', { name: /15 Oct 2026|Oct 15, 2026/ }));
    await userEvent.click(day(20)); // userEvent refuses the click if pointer-events are off on the panel
    expect(onChange).toHaveBeenCalledWith('2026-10-20');
  });

  it('disables days before minDate and refuses to pick them', async () => {
    const onChange = vi.fn();
    render(<DatePicker value="2026-10-20" minDate="2026-10-18" onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: /Oct/ }));
    expect(day(15)).toBeDisabled();
    expect(day(17)).toBeDisabled();
    expect(day(18)).toBeEnabled();
    await userEvent.click(day(15));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('Clear empties the value, and is offered only when there is one', async () => {
    const onChange = vi.fn();
    const { unmount } = render(<DatePicker value="2026-10-20" onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: /Oct/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(onChange).toHaveBeenCalledWith('');
    unmount();
    render(<DatePicker value="" onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: /Select date/ }));
    expect(screen.queryByRole('button', { name: 'Clear' })).not.toBeInTheDocument();
  });

  it('Escape closes the panel', async () => {
    render(<DatePicker value="2026-10-20" onChange={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /Oct/ }));
    expect(screen.getByRole('grid')).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('grid')).not.toBeInTheDocument();
  });
});
