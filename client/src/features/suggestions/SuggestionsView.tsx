import { useRef, useState } from 'react';
import { ArrowsClockwise, ListChecks } from '@phosphor-icons/react';
import { PageLoading } from '../../app/components/PageLoading';
import { Alert } from '../../app/components/ui/alert';
import { Button } from '../../app/components/ui/button';
import { EmptyState } from '../../app/components/ui/empty-state';
import { useToast } from '../../app/components/ui/toast';
import { formatDateTime } from '../../app/lib/format';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import type { Me, Suggestion, TeamRecord } from '../../app/types/types';
import { useCurrentUser } from '../../hooks';
import { errorMessage } from '../../services/api';
import { useTeams } from '../admin';
import { AddSuggestionsDialog } from './AddSuggestionsDialog';
import { EditSuggestionDialog } from './EditSuggestionDialog';
import { MemberList } from './MemberList';
import { StandupBlocks } from './StandupBlocks';
import { SuggestionCard } from './SuggestionCard';
import { useRejectSuggestion, useRestoreSuggestion, useSuggestions, useSyncSuggestions } from './hooks';

/** "NPI (Asha Rao)": the team, then the manager who runs it. */
const teamOption = (t: TeamRecord) => `${t.name} (${t.manager?.displayName ?? 'No manager'})`;

/**
 * Who sees which team's suggestions: a manager their own team (and may act on it); an admin any team, picked from a
 * dropdown, read-only unless it is the team they run. The server decides what may be done; this only picks the team.
 */
export function SuggestionsView() {
  const { data: me } = useCurrentUser();
  const teams = useTeams(!!me?.isAdmin);
  const [pickedTeam, setPickedTeam] = useState<string>();

  if (!me) return <PageLoading />;
  if (!me.isManager && !me.isAdmin) {
    return <div className="mx-auto max-w-[720px] p-8"><Alert variant="info" title="Suggestions are for team managers">Only the manager of a team (or an admin, read-only) sees the tasks suggested from its standups.</Alert></div>;
  }
  const ownTeamId = me.isManager ? me.team?.id : undefined;
  const teamId = me.isAdmin ? pickedTeam ?? ownTeamId ?? teams.data?.[0]?.id : ownTeamId;
  if (!teamId) {
    if (me.isAdmin && teams.isError) return <div className="mx-auto max-w-[720px] p-8"><Alert variant="danger" title="Could not load teams">{errorMessage(teams.error)}</Alert></div>;
    if (me.isAdmin && !teams.data) return <PageLoading label="Loading teams…" />;
    return <div className="mx-auto max-w-[720px] p-8"><EmptyState icon={ListChecks} title={me.isAdmin ? 'No teams yet' : 'No team yet'} description={me.isAdmin ? 'Create a team in the Teams portal first.' : 'You do not run a team yet.'} /></div>;
  }
  return <SuggestionsPage key={teamId} me={me} teamId={teamId} canAct={teamId === ownTeamId} teams={me.isAdmin ? teams.data : undefined} onTeam={setPickedTeam} />;
}

interface PageProps {
  me: Me;
  teamId: string;
  /** The caller runs this team: they can sync, tick, edit, reject, restore and add. Otherwise the page only reads. */
  canAct: boolean;
  /** An admin's team dropdown; left out for a manager. */
  teams?: TeamRecord[];
  onTeam: (teamId: string) => void;
}

/**
 * One team's Suggestions: its people down the left; for the chosen person, what they posted in the standup and the
 * tasks proposed from it. Tick the ones you want and Add creates them as tasks; nothing is on the board until then.
 */
function SuggestionsPage({ me, teamId, canAct, teams, onTeam }: PageProps) {
  const page = useSuggestions(teamId);
  const sync = useSyncSuggestions(teamId);
  // A ref, not `sync.isPending`: a second click in the same frame still sees the old state, and each sync counts against 3 a minute.
  const syncing = useRef(false);
  const reject = useRejectSuggestion();
  const restore = useRestoreSuggestion();
  const { toast } = useToast();
  const [personId, setPersonId] = useState<string>();
  const [ticked, setTicked] = useState<ReadonlySet<string>>(new Set());
  const [editing, setEditing] = useState<Suggestion | null>(null);
  const [reviewing, setReviewing] = useState(false);
  // Due dates typed in the review dialog, kept here so they survive closing it (and a failed Create).
  const [dues, setDues] = useState<Record<string, string>>({});
  const teamName = teams?.find((t) => t.id === teamId)?.name;

  if (page.isError) return <div className="mx-auto max-w-[720px] p-8"><Alert variant="danger" title="Could not load suggestions">{errorMessage(page.error)}</Alert></div>;
  if (!page.data) return <PageLoading label="Loading suggestions…" />;

  const { people, standupChannelId, lastSyncedAt, standupProblem } = page.data;
  const waiting = (p: (typeof people)[number]) => p.suggestions.filter((s) => s.state === 'pending').length;
  const current = people.find((p) => p.person.id === personId) ?? people.find((p) => waiting(p) > 0) ?? people[0];
  // A suggestion that has since been added, rejected or removed cannot stay ticked.
  const pendingIds = new Set(people.flatMap((p) => p.suggestions.filter((s) => s.state === 'pending').map((s) => s.id)));
  const live = new Set([...ticked].filter((id) => pendingIds.has(id)));
  const groups = people.map((p) => ({ person: p.person, suggestions: p.suggestions.filter((s) => live.has(s.id)) })).filter((g) => g.suggestions.length > 0);
  const busy = reject.isPending || restore.isPending;
  const nameOf = (id: string) => people.find((p) => p.person.id === id)?.person.displayName ?? '';
  // The ones still to decide on top, then rejected, then the ones already added to the board at the bottom (sort is stable).
  const rank: Record<Suggestion['state'], number> = { pending: 0, rejected: 1, approved: 2 };
  const ordered = current ? [...current.suggestions].sort((a, b) => rank[a.state] - rank[b.state]) : [];

  const toggle = (id: string) => setTicked((t) => { const next = new Set(t); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const untick = (id: string) => setTicked((t) => { const next = new Set(t); next.delete(id); return next; });
  const fail = (err: unknown) => toast(errorMessage(err), 'warning');
  /** One sync at a time, for everyone or for one person: a second press while one runs does nothing. */
  const runSync = (personId: string | undefined, done: string) => {
    if (syncing.current) return;
    syncing.current = true;
    sync.mutate(personId, { onSuccess: () => toast(done, 'success'), onError: fail, onSettled: () => { syncing.current = false; } });
  };

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5 px-6 py-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">Suggestions</h1>
          <p className="mt-0.5 text-base text-ink-muted">
            {canAct ? 'Tasks found in the standup notes. Tick the ones you want, then review them with Add.' : `Read-only view${teamName ? ` of ${teamName}` : ''}. You can sync it to check the standup connection; only the team’s manager reviews and adds the suggestions.`}
          </p>
          <p className="mt-1 text-sm text-ink-subtle">{lastSyncedAt ? `Last sync ${formatDateTime(lastSyncedAt)}` : 'Not synced yet'}</p>
        </div>
        <div className="flex items-center gap-2">
          {teams && (
            <div className="w-[300px]">
              <Select value={teamId} onValueChange={onTeam}>
                <SelectTrigger aria-label="Team" className="py-2"><SelectValue /></SelectTrigger>
                <SelectContent>{teams.map((t) => <SelectItem key={t.id} value={t.id}>{teamOption(t)}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          )}
          <Button
            variant="outline"
            disabled={sync.isPending || !standupChannelId}
            onClick={() => runSync(undefined, 'Synced from the standup.')}
          >
            <ArrowsClockwise size={14} aria-hidden />{sync.isPending ? 'Syncing…' : 'Sync now'}
          </Button>
          {canAct && <Button disabled={live.size === 0} onClick={() => setReviewing(true)}>Add ({live.size})</Button>}
        </div>
      </div>

      {standupProblem === 'channel_empty' && (
        <Alert variant="info" title="No standup posts found in this team’s channel">
          Nothing has been posted this week in the channel set for this team ({standupChannelId}). Early in the week that is normal. If
          people did post, the channel may not be the one the standup app uses: ask an admin to check it.
        </Alert>
      )}
      {(standupProblem === 'not_configured' || standupProblem === 'unreadable') && (
        <Alert variant="warning" title="The standup posts cannot be shown">
          {standupProblem === 'not_configured'
            ? 'The standup database is not set up on this server. Suggestions already found are still shown below.'
            : 'The standup database could not be opened. Suggestions already found are still shown below.'}
        </Alert>
      )}

      {!standupChannelId ? (
        <EmptyState icon={ListChecks} title="No standup channel yet" description="Ask an admin to set this team’s standup channel. Suggestions are read from it." />
      ) : people.length === 0 ? (
        <EmptyState icon={ListChecks} title="No one on the team yet" description="Add people to the team first; suggestions come from their standup posts." />
      ) : (
        <div className="grid items-start gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
          <MemberList people={people} selectedPersonId={current.person.id} meId={me.user.id} lastSyncedAt={lastSyncedAt} ticked={live} onSelect={setPersonId} />
          <div className="flex min-w-0 flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-md font-semibold text-ink">{current.person.displayName}{current.person.id === me.user.id && <span className="font-normal text-ink-subtle"> (you)</span>}</h2>
              <Button
                size="sm"
                variant="outline"
                disabled={sync.isPending || !standupChannelId}
                onClick={() => runSync(current.person.id, `Synced ${current.person.displayName}.`)}
              >
                <ArrowsClockwise size={14} aria-hidden />{sync.isPending && sync.variables === current.person.id ? 'Syncing…' : `Sync ${current.person.displayName}`}
              </Button>
            </div>
            <StandupBlocks post={current.standup} unavailable={standupProblem === 'not_configured' || standupProblem === 'unreadable'} />
            {current.suggestions.length === 0 ? (
              <p className="py-8 text-center text-base text-ink-muted">No suggestions for {current.person.displayName}.</p>
            ) : (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(380px,1fr))] gap-3.5">
                {ordered.map((s) => (
                  <SuggestionCard
                    key={s.id}
                    suggestion={s}
                    assigneeName={nameOf(s.personId)}
                    selected={live.has(s.id)}
                    busy={busy}
                    readOnly={!canAct}
                    onToggle={() => toggle(s.id)}
                    onEdit={() => setEditing(s)}
                    onReject={() => reject.mutate(s.id, { onSuccess: () => { untick(s.id); toast('Rejected. You can restore it for 3 days.'); }, onError: fail })}
                    onRestore={() => restore.mutate(s.id, { onError: fail })}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <EditSuggestionDialog
        suggestion={editing}
        assignees={people.map((p) => ({ id: p.person.id, displayName: p.person.displayName }))}
        onClose={() => setEditing(null)}
        onSaved={(id) => setTicked((t) => new Set(t).add(id))}
      />
      {reviewing && (
        <AddSuggestionsDialog
          teamId={teamId}
          groups={groups}
          dues={dues}
          onDueChange={(id, due) => setDues((d) => ({ ...d, [id]: due }))}
          onClose={() => setReviewing(false)}
          onAdded={(n) => { setTicked(new Set()); setDues({}); toast(`${n} ${n === 1 ? 'task' : 'tasks'} added to the board.`, 'success'); }}
        />
      )}
    </div>
  );
}
