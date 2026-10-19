import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Select, SelectContent, SelectItem, SelectSearchInput, SelectTrigger, SelectValue } from './select';

function setup(onValueChange = vi.fn(), onSearch = vi.fn()) {
  render(
    <Select value="" onValueChange={onValueChange}>
      <SelectTrigger aria-label="Person"><SelectValue placeholder="Choose" /></SelectTrigger>
      <SelectContent>
        <SelectSearchInput value="" onValueChange={onSearch} aria-label="Search people" />
        <SelectItem value="a">Ann</SelectItem>
        <SelectItem value="b">Bo</SelectItem>
      </SelectContent>
    </Select>,
  );
  return { onValueChange, onSearch };
}

describe('searchable Select', () => {
  it('ArrowDown from the search box highlights the first option, and Enter picks it', async () => {
    const { onValueChange } = setup();
    await userEvent.click(screen.getByRole('combobox', { name: 'Person' }));
    await userEvent.click(await screen.findByRole('textbox', { name: 'Search people' }));
    await userEvent.keyboard('{ArrowDown}');
    expect(await screen.findByRole('option', { name: 'Ann' })).toHaveAttribute('data-highlighted');
    await userEvent.keyboard('{Enter}');
    expect(onValueChange).toHaveBeenCalledWith('a');
  });

  it('typing in the search box reports the text and does not pick anything', async () => {
    const { onValueChange, onSearch } = setup();
    await userEvent.click(screen.getByRole('combobox', { name: 'Person' }));
    await userEvent.type(await screen.findByRole('textbox', { name: 'Search people' }), 'b');
    expect(onSearch).toHaveBeenCalledWith('b');
    expect(onValueChange).not.toHaveBeenCalled();
  });

  it('clicking an option picks it', async () => {
    const { onValueChange } = setup();
    await userEvent.click(screen.getByRole('combobox', { name: 'Person' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Bo' }));
    expect(onValueChange).toHaveBeenCalledWith('b');
  });
});
