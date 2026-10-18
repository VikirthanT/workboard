import { useEffect, useState } from 'react';
import { Label } from '../../app/components/ui/label';
import { Select, SelectContent, SelectItem, SelectSearchInput, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import { useToast } from '../../app/components/ui/toast';
import type { PersonRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { ReasonFormDialog } from '../team';
import { useAdminCandidates, useSetAdmin } from './hooks';

/**
 * Make anyone in the directory an admin, whether or not they are on a team: an admin may be only an admin. People who
 * already are admins are left out of the list. The reason is required and kept in the audit log.
 */
export function AddAdminDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState('');
  const candidates = useAdminCandidates(open, q);
  const set = useSetAdmin();
  const { toast } = useToast();
  const [chosen, setChosen] = useState<PersonRecord | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  useEffect(() => { if (open) { setChosen(null); setQ(''); } setPickerOpen(open); }, [open]);

  const list = (candidates.data ?? []).filter((p) => !p.isAdmin);

  return (
    <ReasonFormDialog
      open={open}
      title="Add an admin"
      description="Admins create teams, change managers and admins, and read every board. They do not need to be on a team."
      placeholder="Why do they need admin access?"
      submitLabel="Make admin"
      busy={set.isPending}
      autoFocusReason={false}
      onClose={onClose}
      onSubmit={(reason, fail) => {
        if (!chosen) return fail('Choose a person first.');
        set.mutate(
          { personId: chosen.id, isAdmin: true, reason },
          { onSuccess: () => { toast(`${chosen.displayName} is now an admin.`, 'success'); onClose(); }, onError: (e) => fail(errorMessage(e)) },
        );
      }}
    >
      <div>
        <Label htmlFor="admin-person">Person</Label>
        <Select open={pickerOpen} onOpenChange={setPickerOpen} value={chosen?.id ?? ''} onValueChange={(id) => setChosen(list.find((p) => p.id === id) ?? chosen)}>
          <SelectTrigger id="admin-person" className="mt-2"><SelectValue placeholder="Choose a person">{chosen ? `${chosen.displayName} (${chosen.email})` : undefined}</SelectValue></SelectTrigger>
          <SelectContent>
            <SelectSearchInput value={q} onValueChange={setQ} placeholder="Search by name or email" aria-label="Search people" />
            {list.map((p) => <SelectItem key={p.id} value={p.id}>{p.displayName} ({p.email})</SelectItem>)}
            {list.length === 0 && (
              <p className="px-3 py-2 text-sm text-ink-subtle">{candidates.isError ? errorMessage(candidates.error) : candidates.data ? 'No one matches.' : 'Loading…'}</p>
            )}
          </SelectContent>
        </Select>
      </div>
    </ReasonFormDialog>
  );
}
