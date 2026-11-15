import { useEffect, useState } from 'react';
import { Alert } from '../../app/components/ui/alert';
import { Button } from '../../app/components/ui/button';
import { CheckboxField } from '../../app/components/ui/checkbox';
import type { ChannelMember } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { ReasonFormDialog } from './ReasonFormDialog';
import { useAddMembers, useChannelMembers } from './hooks';

interface Props {
  /** The team to pull into; null closes the dialog. */
  team: { id: string; name: string } | null;
  /** A manager need not give a reason for adding to their own team. */
  reasonOptional?: boolean;
  onClose: (added?: number) => void;
}

/** Why a person in the channel cannot be ticked. */
const whyNot = (m: ChannelMember): string =>
  m.state === 'on_this_team' ? 'Already on this team' : m.state === 'on_other_team' ? `On ${m.teamName ?? 'another team'}` : 'Cannot be added (inactive, or a manager)';

/**
 * Review before adding: everyone in the team's Slack channel who is in the directory. People who can join are ticked; the
 * rest say why not. Nothing is added until the person confirms, and then the ticked people join together or not at all.
 * If the channel is not set, cannot be found or the bot is not in it, the dialog says exactly that (the server's words).
 */
export function PullFromSlackDialog({ team, reasonOptional, onClose }: Props) {
  const found = useChannelMembers(team?.id ?? '', !!team);
  const add = useAddMembers(team?.id ?? '');
  const [ticked, setTicked] = useState<ReadonlySet<string>>(new Set());

  const members = found.data?.members ?? [];
  const available = members.filter((m) => m.state === 'available');
  useEffect(() => { setTicked(new Set(found.data?.members.filter((m) => m.state === 'available').map((m) => m.person.id))); }, [found.data]);

  const toggle = (id: string) => setTicked((t) => { const next = new Set(t); if (next.has(id)) next.delete(id); else next.add(id); return next; });

  return (
    <ReasonFormDialog
      open={!!team}
      title={`Pull people from Slack into ${team?.name ?? ''}`}
      description="These are the people in the team's standup channel. Tick who should join the team, then add them."
      placeholder="Why are they joining? (optional)"
      submitLabel={`Add ${ticked.size} ${ticked.size === 1 ? 'person' : 'people'}`}
      reasonOptional={reasonOptional}
      busy={add.isPending || found.isPending || !!found.error}
      autoFocusReason={false}
      onClose={() => onClose()}
      onSubmit={(reason, fail) => {
        if (ticked.size === 0) return fail('Tick at least one person to add.');
        add.mutate({ personIds: [...ticked], reason }, { onSuccess: () => onClose(ticked.size), onError: (e) => fail(errorMessage(e)) });
      }}
    >
      {found.isPending && <p className="text-base text-ink-subtle">Reading the Slack channel…</p>}
      {found.isError && <Alert variant="warning" title="The channel could not be read">{errorMessage(found.error)}</Alert>}
      {found.data && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3 text-sm text-ink-muted">
            <span>{available.length} can join · {members.length - available.length} cannot{found.data.notInDirectory > 0 ? ` · ${found.data.notInDirectory} not in the directory` : ''}</span>
            {available.length > 0 && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setTicked(ticked.size === available.length ? new Set() : new Set(available.map((m) => m.person.id)))}>
                {ticked.size === available.length ? 'Untick all' : 'Tick all'}
              </Button>
            )}
          </div>
          {members.length === 0 ? (
            <p className="py-4 text-center text-base text-ink-muted">No one in this channel is in the directory.</p>
          ) : (
            <ul className="flex max-h-[320px] flex-col overflow-y-auto rounded-lg border border-line">
              {members.map((m) => (
                <li key={m.person.id} className="flex items-center justify-between gap-3 border-b border-line px-3 py-2 last:border-b-0">
                  <CheckboxField
                    label={<span className="flex flex-col"><span className="text-base text-ink">{m.person.displayName}</span><span className="text-xs text-ink-subtle">{m.person.email}</span></span>}
                    checked={m.state === 'available' && ticked.has(m.person.id)}
                    disabled={m.state !== 'available'}
                    onCheckedChange={() => toggle(m.person.id)}
                  />
                  {m.state !== 'available' && <span className="shrink-0 text-sm text-ink-subtle">{whyNot(m)}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </ReasonFormDialog>
  );
}
