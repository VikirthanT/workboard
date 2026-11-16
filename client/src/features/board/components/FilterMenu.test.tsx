import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FilterMenu } from './FilterMenu';

const OPTIONS = ['needs_review', 'overdue', 'blocked', 'due_week'] as const;

function setup(over: Partial<React.ComponentProps<typeof FilterMenu>> = {}) {
  const fns = { onToggle: vi.fn(), onClear: vi.fn(), onAttention: vi.fn() };
  render(
    <FilterMenu
      options={[...OPTIONS]}
      selected={[]}
      counts={{ needs_review: 2, overdue: 1, blocked: 0, due_week: 3 }}
      attention={{ checked: false, count: 4, onChange: fns.onAttention }}
      onToggle={fns.onToggle}
      onClear={fns.onClear}
      {...over}
    />,
  );
  return fns;
}

const open = () => userEvent.click(screen.getByRole('button', { name: 'Filters' }));

describe('FilterMenu', () => {
  it('lists "Needs attention" first with its count, then the filters, "Needs my review" among them', async () => {
    setup();
    await open();

    const items = screen.getAllByRole('menuitemcheckbox').map((i) => i.textContent);
    expect(items[0]).toMatch(/^Needs attention4/);
    expect(items.some((t) => t?.startsWith('Needs my review2'))).toBe(true);
    expect(items).toHaveLength(5);
  });

  it('turns "Needs attention" on and off through its own switch, and the menu stays open', async () => {
    const { onAttention, onToggle } = setup();
    await open();

    await userEvent.click(screen.getByRole('menuitemcheckbox', { name: /Needs attention/ }));

    expect(onAttention).toHaveBeenCalledWith(true);
    expect(onToggle).not.toHaveBeenCalled();
    expect(screen.getByRole('menuitemcheckbox', { name: /^Overdue/ })).toBeInTheDocument(); // still open
  });

  it('shows an active "Needs attention" as a chip, counts it on the button, and removes it from the chip', async () => {
    const onAttention = vi.fn();
    setup({ attention: { checked: true, count: 4, onChange: onAttention }, selected: ['overdue'] });

    expect(screen.getByRole('button', { name: 'Filters' })).toHaveTextContent('2'); // attention and overdue
    await userEvent.click(screen.getByRole('button', { name: 'Remove filter Needs attention' }));

    expect(onAttention).toHaveBeenCalledWith(false);
    expect(screen.getByRole('button', { name: 'Remove filter Overdue' })).toBeInTheDocument();
  });

  it('offers "Clear all filters" when only "Needs attention" is on', async () => {
    const { onClear } = setup({ attention: { checked: true, count: 4, onChange: vi.fn() } });
    await open();

    await userEvent.click(screen.getByRole('menuitem', { name: 'Clear all filters' }));

    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('still works as a plain filter menu when no attention switch is given', async () => {
    setup({ attention: undefined });
    await open();

    expect(screen.queryByRole('menuitemcheckbox', { name: /Needs attention/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole('menuitemcheckbox')).toHaveLength(4);
  });
});
