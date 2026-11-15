import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { BoardSearch } from './BoardSearch';

afterEach(() => vi.useRealTimers());

describe('BoardSearch', () => {
  it('sends what was typed only after a short pause', () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(<BoardSearch value="" onChange={onChange} />);

    fireEvent.change(screen.getByLabelText('Search tasks'), { target: { value: 'weld' } });
    expect(onChange).not.toHaveBeenCalled();
    act(() => void vi.advanceTimersByTime(300));
    expect(onChange).toHaveBeenCalledWith('weld');
  });

  it('clears at once with the clear button', () => {
    const onChange = vi.fn();
    render(<BoardSearch value="#33" onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }));
    expect(onChange).toHaveBeenCalledWith('');
    expect(screen.getByLabelText('Search tasks')).toHaveValue('');
  });
});
