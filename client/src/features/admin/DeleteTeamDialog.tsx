import { useEffect, useState } from 'react';
import { Input } from '../../app/components/ui/input';
import { Label } from '../../app/components/ui/label';
import { useToast } from '../../app/components/ui/toast';
import type { TeamRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { ReasonFormDialog } from '../team';
import { useDeleteTeam } from './hooks';

/** Irreversible, so the admin types the team's name first (the server checks it too) and gives a reason. */
export function DeleteTeamDialog({ team, onClose }: { team: TeamRecord | null; onClose: () => void }) {
  const del = useDeleteTeam();
  const { toast } = useToast();
  const [typed, setTyped] = useState('');
  useEffect(() => { setTyped(''); }, [team]);

  return (
    <ReasonFormDialog
      open={!!team}
      title={`Delete ${team?.name}?`}
      description="This cannot be undone. Its people return to no team and its tasks are erased."
      placeholder="Why is this team being deleted?"
      submitLabel="Delete team"
      destructive
      busy={del.isPending}
      onClose={onClose}
      onSubmit={(reason, fail) => {
        if (typed.trim().toLowerCase() !== team!.name.trim().toLowerCase()) return fail('Type the team’s name to confirm.');
        del.mutate(
          { teamId: team!.id, confirmName: typed.trim(), reason },
          { onSuccess: () => { toast(`${team!.name} deleted.`, 'success'); onClose(); }, onError: (e) => fail(errorMessage(e)) },
        );
      }}
    >
      <div>
        <Label htmlFor="confirm-team-name">Type <strong>{team?.name}</strong> to confirm</Label>
        <Input id="confirm-team-name" className="mt-2" autoFocus autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} />
      </div>
    </ReasonFormDialog>
  );
}
