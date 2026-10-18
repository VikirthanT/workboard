import { useToast } from '../../app/components/ui/toast';
import type { PersonRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { ReasonFormDialog } from './ReasonFormDialog';
import { useRemoveMember } from './hooks';

/**
 * Take a person off a team (the dustbin). Render it only while someone is being removed. A manager need not give a
 * reason; an admin must, and the server says so if it is missing.
 */
export function RemoveMemberDialog({ team, person, reasonOptional, onClose }: {
  team: { id: string; name: string }; person: PersonRecord; reasonOptional: boolean; onClose: () => void;
}) {
  const remove = useRemoveMember(team.id);
  const { toast } = useToast();
  return (
    <ReasonFormDialog
      open
      title={`Remove ${person.displayName} from ${team.name}?`}
      description={person.email}
      placeholder="Why are they leaving the team?"
      submitLabel="Remove from team"
      destructive
      reasonOptional={reasonOptional}
      busy={remove.isPending}
      onClose={onClose}
      onSubmit={(reason, fail) =>
        remove.mutate(
          { personId: person.id, reason },
          { onSuccess: () => { toast(`${person.displayName} removed.`, 'success'); onClose(); }, onError: (e) => fail(errorMessage(e)) },
        )
      }
    >
      <p className="text-base text-ink-muted">
        They go back to the directory and can join another team. Their open tasks stay on the board and show as needing a new owner.
      </p>
    </ReasonFormDialog>
  );
}
