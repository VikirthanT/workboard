import { UsersThree } from '@phosphor-icons/react';
import { EmptyState } from '../../app/components/ui/empty-state';

/** Shown instead of a board to anyone who signs in without a team. Only an admin can put them on one. */
export function NoTeamPage() {
  return (
    <div className="mx-auto max-w-[720px] px-6 py-16">
      <EmptyState
        icon={UsersThree}
        title="You are not on any team yet"
        description="Ask an admin to make you the manager of a team. Once they do, you can add your people and start assigning work."
      />
    </div>
  );
}
