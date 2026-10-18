import { useState } from 'react';
import { PageLoading } from '../../app/components/PageLoading';
import { Alert } from '../../app/components/ui/alert';
import type { PersonRecord, TeamRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { AddMemberDialog } from './AddMemberDialog';
import { filterMembers, type RoleFilter } from './memberFilter';
import { PeopleFilters } from './PeopleFilters';
import { PeopleHeader } from './PeopleHeader';
import { RemoveMemberDialog } from './RemoveMemberDialog';
import { TeamSection } from './TeamSection';
import { useTeamMembers } from './hooks';

/**
 * The manager's own team: search, add from the directory, remove with the dustbin. Roles and admin access are the
 * admin's to change, so those controls are not drawn here. A manager need not give a reason for either change.
 */
export function TeamMembersPanel({ team }: { team: { id: string; name: string } }) {
  const members = useTeamMembers(team.id);
  const [search, setSearch] = useState('');
  const [role, setRole] = useState<RoleFilter>('all');
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<PersonRecord | null>(null);

  if (members.isError) return <Alert variant="danger" title="Could not load the team">{errorMessage(members.error)}</Alert>;
  if (!members.data) return <PageLoading label="Loading the team…" />;
  const all = members.data;
  const manager = all.find((p) => p.role === 'manager');
  const record: TeamRecord = {
    id: team.id,
    name: team.name,
    manager: manager ? { id: manager.id, displayName: manager.displayName, email: manager.email, active: manager.active } : null,
    memberCount: all.length,
  };

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-raised">
      <PeopleFilters search={search} onSearch={setSearch} role={role} onRole={setRole} />
      <PeopleHeader adminControls={false} />
      <TeamSection team={record} members={filterMembers(all, search, role)} totalMembers={all.length} onAdd={() => setAdding(true)} onRemove={setRemoving} />
      <AddMemberDialog open={adding} teamId={team.id} teamName={team.name} reasonOptional onClose={() => setAdding(false)} />
      {removing && <RemoveMemberDialog team={team} person={removing} reasonOptional onClose={() => setRemoving(null)} />}
    </div>
  );
}
