
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogCloseButton } from '../../app/components/ui/dialog';
import { useDevAccounts } from './hooks';

const ROW = 'flex w-full cursor-pointer flex-col rounded-md border-none bg-transparent px-3 py-2 text-left transition-colors hover:bg-surface-hover focus-ring';

/* DEV ONLY: stands in for Google's account chooser. LoginPage renders it only under `import.meta.env.DEV`, so a
   production build drops it, and everything only it uses, from the bundle (scripts/test_all.py checks that). */
export function DevAccountChooser({ open, onOpenChange, onPick, onGoogle }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (email: string) => void;
  onGoogle: () => void;
}) {
  const accounts = useDevAccounts(open);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[420px]">
        <DialogHeader>
          <div>
            <DialogTitle>Choose an account</DialogTitle>
            <DialogDescription>Development only, in place of Google. Pick who you want to be.</DialogDescription>
          </div>
          <DialogCloseButton />
        </DialogHeader>
        <DialogBody className="p-2">
          {accounts.isLoading && <p className="p-3 text-sm text-ink-subtle">Loading…</p>}
          <ul>
            {accounts.data?.map((a) => (
              <li key={a.email}>
                <button type="button" onClick={() => onPick(a.email)} className={ROW}>
                  <span className="text-base font-medium text-ink">{a.name}</span>
                  <span className="text-sm text-ink-subtle">{a.email}</span>
                  {a.note && <span className="mt-0.5 text-sm text-warning-ink">{a.note}</span>}
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-1 border-t border-line pt-1">
            <button type="button" onClick={onGoogle} className={ROW}>
              <span className="text-base font-medium text-ink">Sign in with real Google</span>
              <span className="text-sm text-ink-subtle">Opens Google. Needs the Google settings in .env (see .env.example).</span>
            </button>
          </div>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}
