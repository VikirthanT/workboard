import { useToast } from '../../app/components/ui/toast';
import type { PersonRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { ReasonFormDialog } from '../team';
import { useChangeManager, useSetAdmin } from './hooks';

/** Make a member the team's manager. The old manager stays on the team as a member. Render only while it is open. */
export function ManagerChangeDialog({ team, person, onClose }: { team: { id: string; name: string }; person: PersonRecord; onClose: () => void }) {
  const change = useChangeManager();
  const { toast } = useToast();
  return (
    <ReasonFormDialog
      open
      title={`Make ${person.displayName} the manager of ${team.name}?`}
      description="The current manager becomes a member and stays on the team."
      placeholder="Why is the manager changing?"
      submitLabel="Make manager"
      busy={change.isPending}
      onClose={onClose}
      onSubmit={(reason, fail) =>
        change.mutate(
          { teamId: team.id, personId: person.id, reason },
          { onSuccess: () => { toast(`${person.displayName} now manages ${team.name}.`, 'success'); onClose(); }, onError: (e) => fail(errorMessage(e)) },
        )
      }
    />
  );
}

/** Make or revoke admin. The server refuses to revoke the last active admin; its message shows in the dialog. */
export function AdminToggleDialog({ person, isAdmin, onClose }: { person: PersonRecord; isAdmin: boolean; onClose: () => void }) {
  const set = useSetAdmin();
  const { toast } = useToast();
  return (
    <ReasonFormDialog
      open
      title={isAdmin ? `Make ${person.displayName} an admin?` : `Revoke admin from ${person.displayName}?`}
      description={isAdmin ? 'Admins create and delete teams, change managers and read every board.' : 'They keep their team role but lose admin access.'}
      placeholder="Why is this changing?"
      submitLabel={isAdmin ? 'Make admin' : 'Revoke admin'}
      destructive={!isAdmin}
      busy={set.isPending}
      onClose={onClose}
      onSubmit={(reason, fail) =>
        set.mutate(
          { personId: person.id, isAdmin, reason },
          { onSuccess: () => { toast(isAdmin ? `${person.displayName} is now an admin.` : `Admin revoked from ${person.displayName}.`, 'success'); onClose(); }, onError: (e) => fail(errorMessage(e)) },
        )
      }
    />
  );
}
