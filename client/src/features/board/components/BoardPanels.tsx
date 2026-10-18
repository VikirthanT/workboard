import { Warning } from '@phosphor-icons/react';
import { Button } from '../../../app/components/ui/button';
import { Alert } from '../../../app/components/ui/alert';
import type { Task } from '../../../app/types/types';

/** Open tasks whose assignee is inactive or no longer on the team. The manager needs to reassign them. */
export function OrphanBanner({ tasks, onOpen, readOnly = false }: { tasks: Task[]; onOpen: (id: string) => void; readOnly?: boolean }) {
  if (!tasks.length) return null;
  return (
    <Alert variant="warning" title={`${tasks.length} open ${tasks.length === 1 ? 'task needs' : 'tasks need'} a new owner`}>
      <p className="mb-2">Their assignee is inactive or off the team. {readOnly ? "The team's manager can reassign them." : 'Open each one to reassign it.'}</p>
      <ul className="flex flex-wrap gap-2">
        {tasks.map((t) => (
          <li key={t.id}>
            <Button variant="outline" size="sm" onClick={() => onOpen(t.id)}>
              <Warning size={12} aria-hidden />
              {t.title}
            </Button>
          </li>
        ))}
      </ul>
    </Alert>
  );
}

