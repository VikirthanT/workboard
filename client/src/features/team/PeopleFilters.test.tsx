import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PeopleFilters } from './PeopleFilters';
import { PeopleHeader } from './PeopleHeader';

describe('PeopleFilters', () => {
  it('reports each typed character to onSearch and shows the current value', async () => {
    const onSearch = vi.fn();
    render(<PeopleFilters search="" onSearch={onSearch} role="all" onRole={() => {}} />);
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search people' }), 'an');
    expect(onSearch).toHaveBeenNthCalledWith(1, 'a');
    expect(onSearch).toHaveBeenNthCalledWith(2, 'n'); // controlled: the value prop did not change
  });

  it('shows the selected role and offers all four', async () => {
    const onRole = vi.fn();
    render(<PeopleFilters search="" onSearch={() => {}} role="manager" onRole={onRole} />);
    const trigger = screen.getByRole('combobox', { name: 'Filter by role' });
    expect(trigger).toHaveTextContent('Managers');
    await userEvent.click(trigger);
    expect(await screen.findAllByRole('option')).toHaveLength(4);
    await userEvent.click(screen.getByRole('option', { name: 'Admins' }));
    expect(onRole).toHaveBeenCalledWith('admin');
  });
});

describe('PeopleHeader', () => {
  it('shows the Admin column only with admin controls', () => {
    const { rerender } = render(<PeopleHeader adminControls={false} />);
    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
    expect(screen.getByText('Role')).toBeInTheDocument();
    rerender(<PeopleHeader adminControls />);
    expect(screen.getByText('Admin')).toBeInTheDocument();
  });
});
