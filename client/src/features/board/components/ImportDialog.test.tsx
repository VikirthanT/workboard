import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ImportDialog } from './ImportDialog';

const h = vi.hoisted(() => ({ upload: vi.fn(), check: vi.fn() }));
vi.mock('../hooks', () => ({
  useImportTasks: () => ({ mutate: h.upload, isPending: false }),
  usePreviewImport: () => ({ mutate: h.check, isPending: false }),
}));

const file = new File(['x'], 'tasks.xlsx');
const choose = (f = file) => userEvent.upload(screen.getByLabelText(/Choose the filled-in file/), f);
const row = (n: number, title: string) => ({ row: n, title, description: `About ${title}`, priority: 'high', assignee: 'Ravi', support: null, project: 'P1', stage: 'Design', startAt: '2030-01-01', dueAt: null });

beforeEach(() => { h.upload.mockReset(); h.check.mockReset(); }); // braces: a returned function would be run by vitest as a cleanup hook

describe('ImportDialog', () => {
  it('lists the tasks first and adds them only when confirmed', async () => {
    const onClose = vi.fn();
    h.check.mockImplementation((_f, o) => { o.onSuccess([row(2, 'Order parts'), row(3, 'Fit harness')]); o.onSettled(); });
    h.upload.mockImplementation((_f, o) => { o.onSuccess(2); o.onSettled(); });
    render(<ImportDialog open onClose={onClose} />);
    expect(screen.getByRole('button', { name: 'Proceed' })).toBeDisabled();

    await choose();
    await userEvent.click(screen.getByRole('button', { name: 'Proceed' }));

    expect(h.upload).not.toHaveBeenCalled();
    const table = screen.getByRole('table', { name: 'Tasks to add' });
    expect(table).toHaveTextContent('Order parts');
    expect(table).toHaveTextContent('Fit harness');
    await userEvent.click(screen.getByRole('button', { name: 'Add 2 tasks' }));
    expect(h.upload).toHaveBeenCalledWith({ file, rows: [2, 3] }, expect.anything());
    expect(onClose).toHaveBeenCalledWith(2);
  });

  it('adds only the ticked tasks, and a click on a task shows its details', async () => {
    h.check.mockImplementation((_f, o) => { o.onSuccess([row(2, 'Order parts'), row(3, 'Fit harness')]); o.onSettled(); });
    render(<ImportDialog open onClose={vi.fn()} />);
    await choose();
    await userEvent.click(screen.getByRole('button', { name: 'Proceed' }));

    await userEvent.click(screen.getByText('Fit harness'));
    expect(screen.getByText('About Fit harness')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Add “Order parts”' }));
    await userEvent.click(screen.getByRole('button', { name: 'Add 1 task' }));
    expect(h.upload).toHaveBeenCalledWith({ file, rows: [3] }, expect.anything());

    await userEvent.click(screen.getByRole('checkbox', { name: 'Tick all' })); // some ticked: ticks every one
    await userEvent.click(screen.getByRole('checkbox', { name: 'Tick all' })); // all ticked: unticks every one
    expect(screen.getByRole('button', { name: 'Add 0 tasks' })).toBeDisabled();
  });

  it('sends the file once however often the button is pressed while it is on its way', async () => {
    render(<ImportDialog open onClose={vi.fn()} />); // h.check never answers: the request stays in flight
    await choose();

    const button = screen.getByRole('button', { name: 'Proceed' });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(h.check).toHaveBeenCalledTimes(1);
  });

  it('Back drops the list without adding anything', async () => {
    h.check.mockImplementation((_f, o) => { o.onSuccess([row(2, 'Order parts')]); o.onSettled(); });
    render(<ImportDialog open onClose={vi.fn()} />);

    await choose();
    await userEvent.click(screen.getByRole('button', { name: 'Proceed' }));
    await userEvent.click(screen.getByRole('button', { name: 'Back' }));

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Proceed' })).toBeEnabled();
    expect(h.upload).not.toHaveBeenCalled();
  });

  it('accepts a dropped .xlsx, shows its name, and lets you remove it', async () => {
    render(<ImportDialog open onClose={vi.fn()} />);
    fireEvent.drop(screen.getByText(/Drop the file here/), { dataTransfer: { files: [file] } });

    expect(screen.getByText('tasks.xlsx')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Proceed' })).toBeEnabled();
    await userEvent.click(screen.getByRole('button', { name: 'Remove file' }));
    expect(screen.getByRole('button', { name: 'Proceed' })).toBeDisabled();
  });

  it('refuses a file that is not .xlsx or is over 2 MB before sending it', () => {
    render(<ImportDialog open onClose={vi.fn()} />);
    const drop = (f: File) => fireEvent.drop(screen.getByText(/Drop the file here/), { dataTransfer: { files: [f] } });

    drop(new File(['x'], 'tasks.csv'));
    expect(screen.getByRole('alert')).toHaveTextContent('.xlsx template');

    drop(new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'big.xlsx'));
    expect(screen.getByRole('alert')).toHaveTextContent('larger than 2 MB');
    expect(screen.getByRole('button', { name: 'Proceed' })).toBeDisabled();
    expect(h.check).not.toHaveBeenCalled();
  });

  it('lists every problem by row and column when the server refuses the file', async () => {
    h.check.mockImplementation((_f, o) => o.onError({ response: { data: { detail: {
      code: 'import_invalid', message: 'Nothing was uploaded.',
      errors: [{ row: 2, column: 'Assignee', message: 'Not on your team.' }, { row: 3, column: '', message: 'Due date is in the past.' }],
    } } } }));
    render(<ImportDialog open onClose={vi.fn()} />);

    await choose();
    await userEvent.click(screen.getByRole('button', { name: 'Proceed' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Nothing was uploaded.');
    const items = screen.getAllByRole('listitem').map((li) => li.textContent);
    expect(items).toEqual(['Row 2, Assignee: Not on your team.', 'Row 3: Due date is in the past.']);
  });
});
