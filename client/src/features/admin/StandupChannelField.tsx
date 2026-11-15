import { useEffect, useState } from 'react';
import { Input } from '../../app/components/ui/input';
import { Label } from '../../app/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import { errorMessage } from '../../services/api';
import { useChannelName, useStandupChannels } from './hooks';

/**
 * The team's standup channel: a picker over the standup app's channels (read live from its database, so a channel added
 * there shows up the next time the list loads), or the Slack channel id typed in. Typing is always possible, because a
 * channel the team uses may not be in the standup app's list (a new or test channel), and it is the only way when that
 * list cannot be loaded (the server has no standup database yet). A typed id shows the channel's name once it is found,
 * or why it cannot be.
 */
export function StandupChannelField({ open, value, onChange }: { open: boolean; value: string; onChange: (id: string) => void }) {
  const channels = useStandupChannels(open);
  const [typing, setTyping] = useState(false);
  const list = channels.data ?? [];
  // Typed ids when asked to, when the list cannot load, or when the current id is not one of the listed channels.
  const typed = typing || channels.isError || (!!value && !!channels.data && !list.some((c) => c.id === value));

  // A typed id is looked up once typing pauses, so the name (or why it cannot be found) shows under the box.
  const [looked, setLooked] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setLooked(typed ? value.trim() : ''), 400);
    return () => clearTimeout(timer);
  }, [typed, value]);
  const name = useChannelName(looked, typed && looked === value.trim());

  return (
    <div>
      <Label htmlFor="team-standup-channel">Standup channel<span aria-hidden className="text-danger"> *</span><span className="sr-only"> (required)</span></Label>
      {typed ? (
        <Input id="team-standup-channel" className="mt-2" autoComplete="off" value={value} onChange={(e) => onChange(e.target.value)} maxLength={32} placeholder="Slack channel id, for example C0123ABCD" />
      ) : (
        <Select value={value} onValueChange={onChange}>
          <SelectTrigger id="team-standup-channel" className="mt-2">
            <SelectValue placeholder={channels.data ? 'Choose a channel' : 'Loading…'}>{value ? (list.find((c) => c.id === value)?.name ?? value) : undefined}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {list.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
      )}
      {typed && looked.length >= 3 && looked === value.trim() && (
        name.data ? (
          <p className="mt-1.5 text-sm text-ink-muted">#{name.data.name}</p>
        ) : name.isError ? (
          <p role="alert" className="mt-1.5 text-sm text-danger-ink">{errorMessage(name.error)}</p>
        ) : (
          <p className="mt-1.5 text-sm text-ink-subtle">Looking up the channel…</p>
        )
      )}
      {channels.data && (
        <button type="button" onClick={() => setTyping(!typed)} className="mt-1.5 cursor-pointer border-none bg-transparent p-0 text-sm text-ink-subtle underline underline-offset-2 hover:text-ink focus-ring">
          {typed ? 'Pick from the standup channels' : 'Use a channel that is not in this list'}
        </button>
      )}
    </div>
  );
}
