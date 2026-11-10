import { Fragment, useEffect, useRef, useState } from 'react';
import { DownloadSimple, FileArrowUp, FileXls, X } from '@phosphor-icons/react';
import { Button } from '../../../app/components/ui/button';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../../app/components/ui/dialog';
import { Checkbox } from '../../../app/components/ui/checkbox';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../app/components/ui/table';
import { formatDay } from '../../../app/lib/format';
import { cn } from '../../../app/lib/utils';
import type { ImportPreviewRow, ImportRowError } from '../../../app/types/types';
import { downloadImportTemplate, errorMessage, importRowErrors } from '../../../services/api';
import { useImportTasks, usePreviewImport } from '../hooks';

const MAX_FILE_BYTES = 2 * 1024 * 1024; // the server's limit

interface Props {
  open: boolean;
  /** `created` is the number of tasks added; undefined when the dialog was just closed. */
  onClose: (created?: number) => void;
}

/**
 * Bulk upload: download the template (its dropdowns are built from the team as it is now), fill it in, upload it.
 * The upload is checked first and its tasks listed; nothing is added until the manager confirms. All or nothing.
 */
export function ImportDialog({ open, onClose }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [rows, setRows] = useState<ImportRowError[]>([]);
  const [preview, setPreview] = useState<ImportPreviewRow[] | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set()); // sheet rows ticked to add
  const [shown, setShown] = useState<number | null>(null); // the row whose details are open
  const [downloading, setDownloading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const sending = useRef(false);
  const check = usePreviewImport();
  const upload = useImportTasks();
  useEffect(() => { if (open) { setFile(null); setMessage(null); setRows([]); setPreview(null); } }, [open]);

  /** Same limits as the server (which checks again), so a wrong file is refused before it is sent. */
  function pick(f: File | undefined) {
    if (!f || sending.current) return; // a file dropped mid-upload would swap what is being checked
    setRows([]);
    setPreview(null);
    if (!f.name.toLowerCase().endsWith('.xlsx')) { setFile(null); setMessage('Choose the .xlsx template, filled in.'); return; }
    if (f.size > MAX_FILE_BYTES) { setFile(null); setMessage('That file is larger than 2 MB.'); return; }
    setFile(f);
    setMessage(null);
  }

  async function download() {
    setDownloading(true);
    setMessage(null);
    try {
      const url = URL.createObjectURL(await downloadImportTemplate());
      const link = document.createElement('a');
      link.href = url;
      link.download = 'workboard-tasks-template.xlsx';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setMessage(errorMessage(err, 'Could not download the template.'));
    } finally {
      setDownloading(false);
    }
  }

  /** First press checks the file and lists its tasks; the second (on the list) adds them. */
  function submit(e: React.FormEvent) {
    e.preventDefault();
    // A ref, not `busy`: a second click in the same frame still sees the old `isPending`.
    if (!file || sending.current) return;
    sending.current = true;
    setMessage(null);
    setRows([]);
    const onError = (err: unknown) => {
      setPreview(null);
      setMessage(errorMessage(err, 'Could not upload the file.'));
      setRows(importRowErrors(err));
    };
    const onSettled = () => { sending.current = false; };
    if (!preview) check.mutate(file, { onSuccess: showPreview, onError, onSettled });
    else upload.mutate({ file, rows: [...picked] }, { onSuccess: (created) => onClose(created), onError, onSettled });
  }

  /** Every task starts ticked; the manager unticks what to leave out. */
  function showPreview(tasks: ImportPreviewRow[]) {
    setPreview(tasks);
    setPicked(new Set(tasks.map((t) => t.row)));
    setShown(null);
  }

  function toggle(row: number) {
    const next = new Set(picked);
    if (!next.delete(row)) next.add(row);
    setPicked(next);
  }

  const busy = check.isPending || upload.isPending;
  const n = picked.size;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className={preview ? 'max-w-4xl' : undefined}>
        <form className="flex min-h-0 flex-col" onSubmit={submit}>
          <DialogHeader>
            <div>
              <DialogTitle>Import tasks</DialogTitle>
              <DialogDescription>Add many tasks at once from a spreadsheet. You see the list before anything is added; if any row has a problem, none are.</DialogDescription>
            </div>
          </DialogHeader>
          <DialogBody>
            <p className="text-sm text-ink-muted">
              1. Download the template. Assignee lists your team; Support lists everyone. Pick people from the dropdowns.
            </p>
            <Button type="button" variant="outline" className="mt-2" disabled={downloading} onClick={download}>
              <DownloadSimple size={14} aria-hidden />
              Download template
            </Button>
            <p className="mt-4 text-sm text-ink-muted">2. Add the filled-in file.</p>
            <div className="mt-2 flex items-stretch gap-2">
              <input id="import-file" type="file" accept=".xlsx" className="peer sr-only" disabled={busy} onChange={(e) => pick(e.target.files?.[0])} />
              <label
                htmlFor="import-file"
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files[0]); }}
                className={cn(
                  'flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-lg border border-dashed px-4 py-4 transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-ring',
                  dragging ? 'border-brand bg-surface-hover' : 'border-line-strong bg-surface-subtle hover:bg-surface-hover',
                )}
              >
                <span className="sr-only">Choose the filled-in file (.xlsx). </span>
                {file ? <FileXls size={28} aria-hidden /> : <FileArrowUp size={28} aria-hidden />}
                <span className="min-w-0 text-sm">
                  {file ? (
                    <>
                      <span className="block truncate font-semibold text-ink">{file.name}</span>
                      <span className="text-ink-muted">{Math.max(1, Math.round(file.size / 1024))} KB. Click to choose another.</span>
                    </>
                  ) : (
                    <>
                      <span className="block font-semibold text-ink">Drop the file here, or click to browse</span>
                      <span className="text-ink-muted">.xlsx only, up to 2 MB</span>
                    </>
                  )}
                </span>
              </label>
              {file && (
                <Button type="button" variant="ghost" aria-label="Remove file" disabled={busy} onClick={() => { setFile(null); setMessage(null); setRows([]); setPreview(null); }}>
                  <X size={14} aria-hidden />
                </Button>
              )}
            </div>
            {message && <p role="alert" className="mt-3 text-sm text-danger-ink">{message}</p>}
            {rows.length > 0 && (
              <ul aria-label="Problems to fix" className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-line px-3 py-2 text-sm text-ink">
                {rows.map((r, i) => (
                  <li key={i} className="py-0.5">
                    <span className="font-semibold">Row {r.row}{r.column ? `, ${r.column}` : ''}:</span> {r.message}
                  </li>
                ))}
              </ul>
            )}
            {preview && (
              <>
                <p className="mt-4 text-sm text-ink">
                  {n} of {preview.length} {preview.length === 1 ? 'task' : 'tasks'} ticked to add; unticked ones are left out. Click a task to see its details. Nothing is saved until you confirm.
                </p>
                <div className="mt-2 max-h-80 overflow-auto rounded-lg border border-line">
                  <Table aria-label="Tasks to add">
                    <TableHeader>
                      <tr>
                        <TableHead className="w-10">
                          <Checkbox
                            aria-label="Tick all"
                            disabled={busy}
                            checked={n === preview.length ? true : n === 0 ? false : 'indeterminate'}
                            onCheckedChange={() => setPicked(new Set(n === preview.length ? [] : preview.map((t) => t.row)))}
                          />
                        </TableHead>
                        <TableHead>Title</TableHead><TableHead>Assignee</TableHead><TableHead>Priority</TableHead><TableHead>Due</TableHead>
                      </tr>
                    </TableHeader>
                    <TableBody>
                      {preview.map((t) => (
                        <Fragment key={t.row}>
                          <TableRow
                            className="cursor-pointer"
                            aria-expanded={shown === t.row}
                            tabIndex={0}
                            onClick={() => setShown(shown === t.row ? null : t.row)}
                            onKeyDown={(e) => { if (e.key === 'Enter') setShown(shown === t.row ? null : t.row); }}
                          >
                            <TableCell onClick={(e) => e.stopPropagation()}>
                              <Checkbox aria-label={`Add “${t.title}”`} disabled={busy} checked={picked.has(t.row)} onCheckedChange={() => toggle(t.row)} />
                            </TableCell>
                            <TableCell className={cn('font-medium', !picked.has(t.row) && 'text-ink-subtle line-through')}>{t.title}</TableCell>
                            <TableCell>{t.assignee}</TableCell>
                            <TableCell className="capitalize">{t.priority}</TableCell>
                            <TableCell className="whitespace-nowrap">{t.dueAt ? formatDay(t.dueAt) : '—'}</TableCell>
                          </TableRow>
                          {shown === t.row && (
                            <TableRow>
                              <TableCell />
                              <TableCell colSpan={4}>
                                <p className="whitespace-pre-wrap text-sm text-ink">{t.description || <span className="text-ink-subtle">No description</span>}</p>
                                <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
                                  {([['Support', t.support], ['Project', t.project], ['Stage', t.stage], ['Start', formatDay(t.startAt)]] as const).map(([label, value]) => (
                                    <div key={label}>
                                      <dt className="text-ink-subtle">{label}</dt>
                                      <dd className="text-ink">{value ?? '—'}</dd>
                                    </div>
                                  ))}
                                </dl>
                              </TableCell>
                            </TableRow>
                          )}
                        </Fragment>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </>
            )}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" disabled={busy} onClick={() => onClose()}>Cancel</Button>
            {preview && <Button type="button" variant="outline" disabled={busy} onClick={() => setPreview(null)}>Back</Button>}
            <Button type="submit" disabled={!file || busy || (!!preview && n === 0)}>
              {check.isPending ? 'Checking…' : upload.isPending ? 'Adding…' : preview ? `Add ${n} ${n === 1 ? 'task' : 'tasks'}` : 'Proceed'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
