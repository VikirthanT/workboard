import { useState } from 'react';
import { CaretDown, Hash, PencilSimple, Plus, SlackLogo, Trash } from '@phosphor-icons/react';
import { Avatar } from '../../app/components/ui/avatar';
import { Button } from '../../app/components/ui/button';
import { Checkbox } from '../../app/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import type { PersonRecord, TeamRecord } from '../../app/types/types';

export interface MemberActions {
  /** Take the person off the team (the dustbin). */
  onRemove: (person: PersonRecord) => void;
  /** Admin only: make this member the team's manager (the old manager becomes a member). */
  onMakeManager?: (person: PersonRecord) => void;
  /** Admin only: make or revoke admin. */
  onToggleAdmin?: (person: PersonRecord, isAdmin: boolean) => void;
}

interface Props extends MemberActions {
  team: TeamRecord;
  /** Already filtered by the search box and role filter. */
  members: PersonRecord[];
  /** How many people the team has before filtering, so a filtered-out section can say so. */
  totalMembers: number;
  onAdd: () => void;
  /** Add people from the team's Slack channel after a review: an admin on any team, a manager on their own. The button is
   *  disabled until the team has a standup channel. Left out when the caller may not (the server refuses it anyway). */
  onPullFromSlack?: () => void;
  /** Admin only: delete the team. Left out for a manager. */
  onDeleteTeam?: () => void;
  /** Change the team's standup channel: an admin on any team, a manager on their own. */
  onEditChannel?: () => void;
  /** The channel's name, when the caller has the channel list; otherwise the header falls back to the id. */
  channelName?: string;
  /** Start folded (a filter with no match in this team). */
  defaultOpen?: boolean;
}

/**
 * One team as a collapsible group: a header with the team, its manager and its actions, then one row per person.
 * Shared by the manager's own page (no role or admin controls) and the admin's Teams portal (all of them).
 */
export function TeamSection({ team, members, totalMembers, onAdd, onPullFromSlack, onDeleteTeam, onEditChannel, channelName, defaultOpen = true, ...actions }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = `team-${team.id}`;
  const filtered = members.length !== totalMembers;

  return (
    <section aria-label={team.name} className="border-t border-line first:border-t-0">
      <div className="flex items-center gap-3 bg-surface-subtle px-5 py-3">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen((o) => !o)}
          className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 border-none bg-transparent p-0 text-left focus-ring"
        >
          <CaretDown size={14} aria-hidden className={open ? 'text-ink-subtle transition-[transform] duration-fast' : '-rotate-90 text-ink-subtle transition-[transform] duration-fast'} />
          <span className="truncate text-base font-semibold text-ink">{team.name}</span>
          <span className="text-sm tabular-nums text-ink-subtle">{filtered ? `${members.length} of ${totalMembers}` : totalMembers}</span>
          <span className="hidden truncate text-sm text-ink-subtle sm:inline">{team.manager ? `Manager: ${team.manager.displayName}` : 'No manager yet'}</span>
        </button>
        {onEditChannel && (
          <button
            type="button"
            aria-label={`Standup channel of ${team.name}`}
            title="Edit standup channel"
            onClick={onEditChannel}
            className="hidden cursor-pointer items-center gap-1.5 border-none bg-transparent p-1 text-sm text-ink-subtle transition-colors hover:text-ink focus-ring md:inline-flex"
          >
            <Hash size={14} aria-hidden />
            {channelName ?? team.standupChannelId ?? 'No standup channel'}
            <PencilSimple size={14} aria-hidden />
          </button>
        )}
        {onPullFromSlack && (
          <Button
            variant="outline"
            size="sm"
            disabled={!team.standupChannelId}
            title={team.standupChannelId ? 'Add people from the team’s Slack channel' : 'Set the team’s standup channel first'}
            onClick={onPullFromSlack}
          >
            <SlackLogo size={14} aria-hidden />Pull from Slack
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={onAdd}><Plus size={14} aria-hidden />Add person</Button>
        {onDeleteTeam && (
          <Button variant="ghost" size="icon" aria-label={`Delete team ${team.name}`} title="Delete team" onClick={onDeleteTeam}>
            <Trash size={16} aria-hidden />
          </Button>
        )}
      </div>

      {open && (
        <ul id={bodyId}>
          {members.map((p) => <MemberRow key={p.id} person={p} {...actions} />)}
          {members.length === 0 && (
            <li className="px-5 py-6 text-center text-sm text-ink-subtle">{totalMembers === 0 ? 'No one on this team yet.' : 'No one here matches.'}</li>
          )}
        </ul>
      )}
    </section>
  );
}

function MemberRow({ person, onRemove, onMakeManager, onToggleAdmin }: { person: PersonRecord } & MemberActions) {
  const isManager = person.role === 'manager';
  return (
    <li className="flex items-center gap-4 border-t border-line px-5 py-3 first:border-t-0">
      <Avatar size="md" name={person.displayName} />
      <div className="min-w-0 flex-1">
        <span className="block truncate font-medium text-ink">{person.displayName}</span>
        <span className="block truncate text-sm text-ink-subtle">{person.email} · {person.slackUserId}</span>
      </div>

      {onToggleAdmin && (
        <div className="flex w-16 justify-center">
          <Checkbox
            checked={person.isAdmin}
            onCheckedChange={(v) => onToggleAdmin(person, v === true)}
            aria-label={`Admin access for ${person.displayName}`}
          />
        </div>
      )}

      {onMakeManager ? (
        // A manager is replaced, never demoted on their own, so their row is fixed and a member's offers Manager.
        <Select value={person.role} disabled={isManager} onValueChange={(v) => v === 'manager' && onMakeManager(person)}>
          <SelectTrigger aria-label={`Role of ${person.displayName}`} className="w-[130px] py-1.5 text-sm"><SelectValue>{isManager ? 'Manager' : 'Member'}</SelectValue></SelectTrigger>
          <SelectContent>
            <SelectItem value="member">Member</SelectItem>
            <SelectItem value="manager">Manager</SelectItem>
          </SelectContent>
        </Select>
      ) : (
        <span className="w-[130px] text-sm text-ink-muted">{isManager ? 'Manager' : 'Member'}</span>
      )}

      <Button
        variant="ghost"
        size="icon"
        disabled={isManager}
        aria-label={isManager ? `${person.displayName} is the manager, replace them first` : `Remove ${person.displayName} from the team`}
        title={isManager ? 'The manager cannot be removed, only replaced' : 'Remove from team'}
        onClick={() => onRemove(person)}
      >
        <Trash size={16} aria-hidden />
      </Button>
    </li>
  );
}
