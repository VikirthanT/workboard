import { useState } from 'react';
import { Plus, Trash } from '@phosphor-icons/react';
import { PageLoading } from '../../app/components/PageLoading';
import { Alert } from '../../app/components/ui/alert';
import { Avatar } from '../../app/components/ui/avatar';
import { Button } from '../../app/components/ui/button';
import type { PersonRecord } from '../../app/types/types';
import { errorMessage } from '../../services/api';
import { AddAdminDialog } from './AddAdminDialog';
import { AdminToggleDialog } from './PersonDialogs';
import { useAdmins } from './hooks';

/**
 * Everyone with admin access, on a team or not. Only an admin can add or remove one, and there is always at least one:
 * with a single admin left their dustbin is locked (the server refuses it too, with `last_admin`).
 */
export function AdminsPanel({ currentUserId }: { currentUserId: string }) {
  const admins = useAdmins();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<PersonRecord | null>(null);

  if (admins.isError) return <Alert variant="danger" title="Could not load the admins">{errorMessage(admins.error)}</Alert>;
  if (!admins.data) return <PageLoading label="Loading admins…" />;
  const list = admins.data;
  const onlyOne = list.length <= 1;

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-raised">
      <div className="flex items-center justify-between gap-3 border-b border-line bg-surface-subtle px-5 py-3">
        <p className="text-base font-semibold text-ink">
          Admins <span className="text-sm font-normal tabular-nums text-ink-subtle">{list.length}</span>
        </p>
        <Button variant="outline" size="sm" onClick={() => setAdding(true)}><Plus size={14} aria-hidden />Add admin</Button>
      </div>
      <ul>
        {list.map((p) => (
          <li key={p.id} className="flex items-center gap-4 border-t border-line px-5 py-3 first:border-t-0">
            <Avatar size="md" name={p.displayName} />
            <div className="min-w-0 flex-1">
              <span className="block truncate font-medium text-ink">{p.displayName}{p.id === currentUserId ? ' (You)' : ''}</span>
              <span className="block truncate text-sm text-ink-subtle">{p.email}</span>
            </div>
            <span className="w-[200px] truncate text-sm text-ink-muted">
              {p.teamName ? `${p.role === 'manager' ? 'Manager' : 'Member'}, ${p.teamName}` : 'No team'}
            </span>
            <Button
              variant="ghost"
              size="icon"
              disabled={onlyOne}
              aria-label={onlyOne ? `${p.displayName} is the only admin` : `Remove admin access from ${p.displayName}`}
              title={onlyOne ? 'There must always be at least one admin' : 'Remove admin access'}
              onClick={() => setRemoving(p)}
            >
              <Trash size={16} aria-hidden />
            </Button>
          </li>
        ))}
      </ul>

      <AddAdminDialog open={adding} onClose={() => setAdding(false)} />
      {removing && <AdminToggleDialog person={removing} isAdmin={false} onClose={() => setRemoving(null)} />}
    </div>
  );
}
