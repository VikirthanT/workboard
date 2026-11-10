import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ImportDialog } from './ImportDialog';

const h = vi.hoisted(() => ({ upload: vi.fn() }));
vi.mock('../hooks', () => ({ useImportTasks: () => ({ mutate: h.upload, isPending: false }) }));

const file = new File(['x'], 'tasks.xlsx');
const choose = (f = file) => userEvent.upload(screen.getByLabelText(/Choose the filled-in file/), f);

beforeEach(() => { h.upload.mockReset(); }); // braces: a returned function would be run by vitest as a cleanup hook

describe('ImportDialog', () => {
  it('keeps Upload disabled until a file is chosen, then uploads it and reports how many were added', async () => {
    const onClose = vi.fn();
    h.upload.mockImplementation((_f, o) => o.onSuccess(3));
    render(<ImportDialog open onClose={onClose} />);
    expect(screen.getByRole('button', { name: 'Upload' })).toBeDisabled();

    await choose();
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }));

    expect(h.upload).toHaveBeenCalledWith(file, expect.anything());
    expect(onClose).toHaveBeenCalledWith(3);
  });

  it('accepts a dropped .xlsx, shows its name, and lets you remove it', async () => {
    render(<ImportDialog open onClose={vi.fn()} />);
    fireEvent.drop(screen.getByText(/Drop the file here/), { dataTransfer: { files: [file] } });

    expect(screen.getByText('tasks.xlsx')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload' })).toBeEnabled();
    await userEvent.click(screen.getByRole('button', { name: 'Remove file' }));
    expect(screen.getByRole('button', { name: 'Upload' })).toBeDisabled();
  });

  it('refuses a file that is not .xlsx or is over 2 MB before sending it', () => {
    render(<ImportDialog open onClose={vi.fn()} />);
    const drop = (f: File) => fireEvent.drop(screen.getByText(/Drop the file here/), { dataTransfer: { files: [f] } });

    drop(new File(['x'], 'tasks.csv'));
    expect(screen.getByRole('alert')).toHaveTextContent('.xlsx template');

    drop(new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'big.xlsx'));
    expect(screen.getByRole('alert')).toHaveTextContent('larger than 2 MB');
    expect(screen.getByRole('button', { name: 'Upload' })).toBeDisabled();
    expect(h.upload).not.toHaveBeenCalled();
  });

  it('lists every problem by row and column when the server refuses the file', async () => {
    h.upload.mockImplementation((_f, o) => o.onError({ response: { data: { detail: {
      code: 'import_invalid', message: 'Nothing was uploaded.',
      errors: [{ row: 2, column: 'Assignee', message: 'Not on your team.' }, { row: 3, column: '', message: 'Due date is in the past.' }],
    } } } }));
    render(<ImportDialog open onClose={vi.fn()} />);

    await choose();
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Nothing was uploaded.');
    const items = screen.getAllByRole('listitem').map((li) => li.textContent);
    expect(items).toEqual(['Row 2, Assignee: Not on your team.', 'Row 3: Due date is in the past.']);
  });
});
