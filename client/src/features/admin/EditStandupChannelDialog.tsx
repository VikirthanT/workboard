import { useEffect, useState } from 'react';
import { useToast } from '../../app/components/ui/toast';
import type { TeamRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { ReasonFormDialog } from '../team';
import { StandupChannelField } from './StandupChannelField';
import { useSetStandupChannel } from './hooks';

/** Change which standup channel a team's suggestions are read from. Audited, so it asks for a reason. */
export function EditStandupChannelDialog({ team, onClose }: { team: TeamRecord | null; onClose: () => void }) {
  const save = useSetStandupChannel();
  const { toast } = useToast();
  const [channel, setChannel] = useState('');
  useEffect(() => { setChannel(team?.standupChannelId ?? ''); }, [team]);

  return (
    <ReasonFormDialog
      open={!!team}
      title={`Standup channel for ${team?.name}`}
      description="Suggestions for this team are read from this channel from now on. Existing suggestions are kept."
      placeholder="Why is the channel changing?"
      submitLabel="Save channel"
      busy={save.isPending}
      autoFocusReason={false}
      onClose={onClose}
      onSubmit={(reason, fail) => {
        if (!channel.trim()) return fail('Choose the team’s standup channel.');
        if (channel.trim() === team!.standupChannelId) return fail('That is already the team’s channel.');
        save.mutate(
          { teamId: team!.id, standupChannelId: channel.trim(), reason },
          { onSuccess: () => { toast(`${team!.name}’s standup channel saved.`, 'success'); onClose(); }, onError: (e) => fail(errorMessage(e)) },
        );
      }}
    >
      <StandupChannelField open={!!team} value={channel} onChange={setChannel} />
    </ReasonFormDialog>
  );
}
