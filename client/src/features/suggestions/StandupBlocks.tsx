import type { StandupPost } from '../../app/types/types';
import { cn } from '../../app/lib/utils';

function Block({ title, text, warn }: { title: string; text: string | null; warn?: boolean }) {
  const has = !!text?.trim();
  return (
    <div className="rounded-lg border border-line bg-surface px-3.5 py-3">
      <h3 className={cn('mb-1.5 text-sm font-semibold', warn && has ? 'text-danger-ink' : 'text-ink-muted')}>{title}</h3>
      <p className={cn('whitespace-pre-line text-sm', has ? 'text-ink' : 'text-ink-subtle')}>{has ? text : 'Nothing posted'}</p>
    </div>
  );
}

/**
 * What the person posted, as three blocks above their suggestions, or a note that they posted nothing. The blocks are
 * the standup's own sections as the standup app stored them: no model is involved. When the posts could not be read at
 * all (`unavailable`) there is nothing to say about this person, and the page explains why once, above.
 */
export function StandupBlocks({ post, unavailable = false }: { post: StandupPost | null; unavailable?: boolean }) {
  if (!post && unavailable) return null;
  if (!post) {
    return (
      <div className="rounded-lg border border-line bg-surface px-3.5 py-3">
        <p className="text-sm text-ink-subtle">No standup posted this week.</p>
      </div>
    );
  }
  // The standup form always has the three sections, so one `message` is only an old or odd post: show it whole.
  if (!post.thisWeek?.trim() && post.message) {
    return <Block title="Standup" text={post.message} />;
  }
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <Block title="Last week" text={post.lastWeek} />
      <Block title="This week" text={post.thisWeek} />
      <Block title="Blockers" text={post.blockers} warn />
    </div>
  );
}
