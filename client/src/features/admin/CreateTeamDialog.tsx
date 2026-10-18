import { useEffect, useState } from 'react';
import { Input } from '../../app/components/ui/input';
import { Label } from '../../app/components/ui/label';
import { Select, SelectContent, SelectItem, SelectSearchInput, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import { useToast } from '../../app/components/ui/toast';
import type { PersonRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { ReasonFormDialog, useUnassignedPeople } from '../team';
import { useCreateTeam } from './hooks';

/** A new team starts with one person from the directory, who becomes its manager; more people are added afterwards. */
export function CreateTeamDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState('');
  const candidates = useUnassignedPeople(open, q);
  const create = useCreateTeam();
  const { toast } = useToast();
  const [name, setName] = useState('');
  const [manager, setManager] = useState<PersonRecord | null>(null);
  useEffect(() => { if (open) { setName(''); setManager(null); setQ(''); } }, [open]);

  const list = candidates.data ?? [];

  return (
    <ReasonFormDialog
      open={open}
      title="Create a team"
      description="The first person you pick becomes the team's manager."
      placeholder="Why is this team being created?"
      submitLabel="Create team"
      busy={create.isPending}
      onClose={onClose}
      onSubmit={(reason, fail) => {
        if (!name.trim()) return fail('Give the team a name.');
        if (!manager) return fail('Choose the team’s first person, who becomes its manager.');
        create.mutate(
          { name: name.trim(), initialManagerPersonId: manager.id, reason },
          { onSuccess: (t) => { toast(`${t.name} created.`, 'success'); onClose(); }, onError: (e) => fail(errorMessage(e)) },
        );
      }}
    >
      <div>
        <Label htmlFor="team-name">Team name</Label>
        <Input id="team-name" className="mt-2" autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="For example, NPI" />
      </div>
      <div>
        <Label htmlFor="team-manager">Manager (first person)</Label>
        <Select value={manager?.id ?? ''} onValueChange={(id) => setManager(list.find((p) => p.id === id) ?? manager)}>
          <SelectTrigger id="team-manager" className="mt-2"><SelectValue placeholder="Choose a person">{manager ? `${manager.displayName} (${manager.email})` : undefined}</SelectValue></SelectTrigger>
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
