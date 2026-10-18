import { useEffect, useState } from 'react';
import { Label } from '../../app/components/ui/label';
import { Select, SelectContent, SelectItem, SelectSearchInput, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import { useToast } from '../../app/components/ui/toast';
import type { PersonRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { ReasonFormDialog } from './ReasonFormDialog';
import { useAddMember, useUnassignedPeople } from './hooks';

/**
 * Pick someone from the directory ("Name (email)") who is on no team yet. A person is on one team only. The list is
 * searched on the server as you type, so it works for a directory of any size. Admins give a reason; a manager need not.
 */
export function AddMemberDialog({ open, teamId, teamName, reasonOptional = false, onClose }: {
  open: boolean; teamId: string; teamName: string; reasonOptional?: boolean; onClose: () => void;
}) {
  const [q, setQ] = useState('');
  const candidates = useUnassignedPeople(open, q);
  const add = useAddMember(teamId);
  const { toast } = useToast();
  const [chosen, setChosen] = useState<PersonRecord | null>(null);
  // The person list opens with the dialog, so typing searches straight away (not the reason below it).
  const [pickerOpen, setPickerOpen] = useState(false);
  useEffect(() => { if (open) { setChosen(null); setQ(''); } setPickerOpen(open); }, [open]);

  const list = candidates.data ?? [];

  return (
    <ReasonFormDialog
      open={open}
      title={`Add to ${teamName}`}
      description="People from the directory who are not on a team yet."
      placeholder="Why are they joining this team?"
      submitLabel="Add to team"
      reasonOptional={reasonOptional}
      busy={add.isPending}
      autoFocusReason={false}
      onClose={onClose}
      onSubmit={(reason, fail) => {
        if (!chosen) return fail('Choose a person first.');
        add.mutate({ personId: chosen.id, reason }, { onSuccess: () => { toast(`${chosen.displayName} joined ${teamName}.`, 'success'); onClose(); }, onError: (e) => fail(errorMessage(e)) });
      }}
    >
      <div>
        <Label htmlFor="member-person">Person</Label>
        <Select open={pickerOpen} onOpenChange={setPickerOpen} value={chosen?.id ?? ''} onValueChange={(id) => setChosen(list.find((p) => p.id === id) ?? chosen)}>
          <SelectTrigger id="member-person" className="mt-2"><SelectValue placeholder="Choose a person">{chosen ? `${chosen.displayName} (${chosen.email})` : undefined}</SelectValue></SelectTrigger>
          <SelectContent>
            <SelectSearchInput value={q} onValueChange={setQ} placeholder="Search by name or email" aria-label="Search people" />
            {list.map((p) => <SelectItem key={p.id} value={p.id}>{p.displayName} ({p.email})</SelectItem>)}
            {list.length === 0 && (
              <p className="px-3 py-2 text-sm text-ink-subtle">
                {candidates.isError ? errorMessage(candidates.error) : candidates.data ? 'No one matches.' : 'Loading…'}
              </p>
            )}
          </SelectContent>
        </Select>
      </div>
    </ReasonFormDialog>
  );
}
