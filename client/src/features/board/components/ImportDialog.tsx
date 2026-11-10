import { useEffect, useState } from 'react';
import { DownloadSimple, FileArrowUp, FileXls, X } from '@phosphor-icons/react';
import { Button } from '../../../app/components/ui/button';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../../app/components/ui/dialog';
import { cn } from '../../../app/lib/utils';
import type { ImportRowError } from '../../../app/types/types';
import { downloadImportTemplate, errorMessage, importRowErrors } from '../../../services/api';
import { useImportTasks } from '../hooks';

const MAX_FILE_BYTES = 2 * 1024 * 1024; // the server's limit

interface Props {
  open: boolean;
  /** `created` is the number of tasks added; undefined when the dialog was just closed. */
  onClose: (created?: number) => void;
}

/** Bulk upload: download the template (its dropdowns are built from the team as it is now), fill it in, upload it. All or nothing. */
export function ImportDialog({ open, onClose }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [rows, setRows] = useState<ImportRowError[]>([]);
  const [downloading, setDownloading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const upload = useImportTasks();
  useEffect(() => { if (open) { setFile(null); setMessage(null); setRows([]); } }, [open]);

  /** Same limits as the server (which checks again), so a wrong file is refused before it is sent. */
  function pick(f: File | undefined) {
    if (!f) return;
    setRows([]);
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

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setMessage(null);
    setRows([]);
    upload.mutate(file, {
      onSuccess: (created) => onClose(created),
      onError: (err) => {
        setMessage(errorMessage(err, 'Could not upload the file.'));
        setRows(importRowErrors(err));
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form className="flex min-h-0 flex-col" onSubmit={submit}>
          <DialogHeader>
            <div>
              <DialogTitle>Import tasks</DialogTitle>
              <DialogDescription>Add many tasks at once from a spreadsheet. If any row has a problem, none are added.</DialogDescription>
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
              <input id="import-file" type="file" accept=".xlsx" className="peer sr-only" onChange={(e) => pick(e.target.files?.[0])} />
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
                <Button type="button" variant="ghost" aria-label="Remove file" onClick={() => { setFile(null); setMessage(null); setRows([]); }}>
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
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onClose()}>Cancel</Button>
            <Button type="submit" disabled={!file || upload.isPending}>{upload.isPending ? 'Uploading…' : 'Upload'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
