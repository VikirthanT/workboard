import { ErrorBoundary } from '../../app/components/ErrorBoundary';
import { PageLoading } from '../../app/components/PageLoading';
import { useCurrentUser } from '../../hooks';
import { NoTeamPage } from './NoTeamPage';
import { TeamMembersPanel } from './TeamMembersPanel';

/** The manager's own team: the people they can assign work to. A new manager lands here first. */
export function TeamView() {
  const { data: me } = useCurrentUser();
  if (!me) return <PageLoading />;
  if (!me.team) return <NoTeamPage />;

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5 px-6 py-6">
      <div>
        <h1 className="font-display text-xl font-semibold text-ink">{me.team.name} team</h1>
        <p className="mt-0.5 text-base text-ink-muted">The people you assign tasks to.</p>
      </div>
      <ErrorBoundary label="The team list">
        <TeamMembersPanel team={me.team} />
      </ErrorBoundary>
    </div>
  );
}
