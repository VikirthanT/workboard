import { useState } from 'react';
import { Plus, UsersThree } from '@phosphor-icons/react';
import { PageLoading } from '../../app/components/PageLoading';
import { Alert } from '../../app/components/ui/alert';
import { Button } from '../../app/components/ui/button';
import { EmptyState } from '../../app/components/ui/empty-state';
import { ErrorBoundary } from '../../app/components/ErrorBoundary';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../app/components/ui/tabs';
import type { PersonRecord, TeamRecord } from '../../app/types/types';
import { useCurrentUser } from '../../hooks';
import { errorMessage } from '../../services/api';
import { AddMemberDialog, filterMembers, PeopleFilters, PeopleHeader, TeamSection, type RoleFilter } from '../team';
import { RemoveMemberDialog } from '../team/RemoveMemberDialog';
import { AdminsPanel } from './AdminsPanel';
import { AuditLog } from './AuditLog';
import { CreateTeamDialog } from './CreateTeamDialog';
import { DeleteTeamDialog } from './DeleteTeamDialog';
import { AdminToggleDialog, ManagerChangeDialog } from './PersonDialogs';
import { useAllTeamMembers, useTeams } from './hooks';

/**
 * The admin's portal: every team as a collapsible group with its people, a search box and role filter, a Manager /
 * Member dropdown and an Admin tick on each person, a dustbin to remove them, and a second tab with the audit log.
 * Every change asks for a reason and is audited.
 */
export function TeamsView() {
  const { data: me } = useCurrentUser();
  const teams = useTeams(!!me?.isAdmin);
  const list = teams.data ?? [];
  const memberQueries = useAllTeamMembers(list);

  const [search, setSearch] = useState('');
  const [role, setRole] = useState<RoleFilter>('all');
  const [creating, setCreating] = useState(false);
  const [adding, setAdding] = useState<TeamRecord | null>(null);
  const [deleting, setDeleting] = useState<TeamRecord | null>(null);
  const [removing, setRemoving] = useState<{ team: TeamRecord; person: PersonRecord } | null>(null);
  const [promoting, setPromoting] = useState<{ team: TeamRecord; person: PersonRecord } | null>(null);
  const [adminChange, setAdminChange] = useState<{ person: PersonRecord; isAdmin: boolean } | null>(null);

  if (!me) return <PageLoading />;
  if (!me.isAdmin) {
    return <div className="mx-auto max-w-[720px] p-8"><Alert variant="danger" title="Admins only">Teams are managed by org admins.</Alert></div>;
  }

  const failed = memberQueries.find((q) => q.isError);
  const loading = !teams.data || memberQueries.some((q) => !q.data && !q.isError);
  const filtering = search.trim() !== '' || role !== 'all';
  const groups = list.map((team, i) => {
    const all = memberQueries[i]?.data ?? [];
    return { team, all, shown: filterMembers(all, search, role) };
  });
  const visible = filtering ? groups.filter((g) => g.shown.length > 0) : groups;
  const people = groups.reduce((n, g) => n + g.all.length, 0);

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5 px-6 py-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">Teams</h1>
          <p className="mt-0.5 text-base text-ink-muted">
            {teams.data ? `${list.length} ${list.length === 1 ? 'team' : 'teams'}, ${people} ${people === 1 ? 'person' : 'people'}` : ''}
          </p>
        </div>
        <Button onClick={() => setCreating(true)}><Plus size={14} aria-hidden />Create team</Button>
      </div>

      <Tabs defaultValue="teams">
        <TabsList>
          <TabsTrigger value="teams">Teams</TabsTrigger>
          <TabsTrigger value="admins">Admins</TabsTrigger>
          <TabsTrigger value="audit">Audit log</TabsTrigger>
        </TabsList>

        <TabsContent value="teams" className="mt-4">
          <ErrorBoundary label="The teams list">
          {teams.isError ? (
            <Alert variant="danger" title="Could not load teams">{errorMessage(teams.error)}</Alert>
          ) : failed ? (
            <Alert variant="danger" title="Could not load a team’s people">{errorMessage(failed.error)}</Alert>
          ) : loading ? (
            <PageLoading label="Loading teams…" />
          ) : list.length === 0 ? (
            <EmptyState icon={UsersThree} title="No teams yet" description="Create the first team: pick a person, who becomes its manager." action={<Button onClick={() => setCreating(true)}>Create team</Button>} />
          ) : (
            <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-raised">
              <PeopleFilters search={search} onSearch={setSearch} role={role} onRole={setRole} />
              <PeopleHeader adminControls />
              {visible.map(({ team, all, shown }) => (
                <TeamSection
                  key={team.id}
                  team={team}
                  members={shown}
                  totalMembers={all.length}
                  onAdd={() => setAdding(team)}
                  onDeleteTeam={() => setDeleting(team)}
                  onRemove={(person) => setRemoving({ team, person })}
                  onMakeManager={(person) => setPromoting({ team, person })}
                  onToggleAdmin={(person, isAdmin) => setAdminChange({ person, isAdmin })}
                />
              ))}
              {visible.length === 0 && <p className="px-5 py-10 text-center text-sm text-ink-subtle">No one matches that search.</p>}
            </div>
          )}
          </ErrorBoundary>
        </TabsContent>

        <TabsContent value="admins" className="mt-4"><ErrorBoundary label="The admins list"><AdminsPanel currentUserId={me.user.id} /></ErrorBoundary></TabsContent>

        <TabsContent value="audit" className="mt-4"><ErrorBoundary label="The audit log"><AuditLog /></ErrorBoundary></TabsContent>
      </Tabs>

      <CreateTeamDialog open={creating} onClose={() => setCreating(false)} />
      <DeleteTeamDialog team={deleting} onClose={() => setDeleting(null)} />
      {adding && <AddMemberDialog open teamId={adding.id} teamName={adding.name} reasonOptional onClose={() => setAdding(null)} />}
      {removing && <RemoveMemberDialog team={removing.team} person={removing.person} reasonOptional={false} onClose={() => setRemoving(null)} />}
      {promoting && <ManagerChangeDialog team={promoting.team} person={promoting.person} onClose={() => setPromoting(null)} />}
      {adminChange && <AdminToggleDialog person={adminChange.person} isAdmin={adminChange.isAdmin} onClose={() => setAdminChange(null)} />}
    </div>
  );
}
