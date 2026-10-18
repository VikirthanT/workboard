import { useEffect, useState } from 'react';
import { Button } from '../../app/components/ui/button';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../app/components/ui/dialog';
import { Label } from '../../app/components/ui/label';
import { Textarea } from '../../app/components/ui/textarea';

interface Props {
  open: boolean;
  title?: string;
  description?: string;
  placeholder: string;
  submitLabel: string;
  destructive?: boolean;
  /** The reason may be left blank (adding a member). */
  reasonOptional?: boolean;
  busy: boolean;
  /** Focus the reason on open (default). Turn off when the dialog's first field is above it. */
  autoFocusReason?: boolean;
  /** Runs with the trimmed reason; call `fail` to show the server's message in the dialog. */
  onSubmit: (reason: string, fail: (message: string) => void) => void;
  onClose: () => void;
  children?: React.ReactNode;
}

/** Every team and membership change is audited, so every one asks for a reason first. */
export function ReasonFormDialog({ open, title, description, placeholder, submitLabel, destructive, reasonOptional, busy, autoFocusReason = true, onSubmit, onClose, children }: Props) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { setReason(''); setError(''); }, [open]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form
          className="flex min-h-0 flex-col"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            if (!reasonOptional && !reason.trim()) return setError('A reason is required for every change.');
            onSubmit(reason.trim(), setError);
          }}
        >
          <DialogHeader>
            <div>
              <DialogTitle>{title}</DialogTitle>
              <DialogDescription>{description}</DialogDescription>
            </div>
          </DialogHeader>
          <DialogBody className="flex flex-col gap-4">
            {children}
            <div>
              <Label htmlFor="change-reason">
                Reason
                {reasonOptional ? ' (optional)' : <><span aria-hidden className="text-danger"> *</span><span className="sr-only"> (required)</span></>}
              </Label>
              <Textarea id="change-reason" className="mt-2" autoFocus={autoFocusReason} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={placeholder} maxLength={500} />
            </div>
            {error && <p role="alert" className="text-sm text-danger-ink">{error}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant={destructive ? 'destructive' : 'default'} disabled={busy || (!reasonOptional && !reason.trim())}>{submitLabel}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
