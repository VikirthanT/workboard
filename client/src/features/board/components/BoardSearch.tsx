import { useEffect, useState } from 'react';
import { MagnifyingGlass, X } from '@phosphor-icons/react';
import { Input } from '../../../app/components/ui/input';

const WAIT_MS = 300;

interface Props {
  value: string;
  onChange: (value: string) => void;
}

/** Search by title or task number (33 or #33). Typing is sent on after a short pause, so the board is not asked on every key. */
export function BoardSearch({ value, onChange }: Props) {
  const [text, setText] = useState(value);

  useEffect(() => {
    if (text === value) return;
    const timer = setTimeout(() => onChange(text), WAIT_MS);
    return () => clearTimeout(timer);
  }, [text, value, onChange]);

  return (
    <div className="relative w-[260px]">
      <MagnifyingGlass size={14} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
      <Input
        type="search"
        aria-label="Search tasks"
        placeholder="Search title or task number"
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="py-2 pl-9 pr-8 text-base [&::-webkit-search-cancel-button]:hidden"
      />
      {text && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => {
            setText('');
            onChange('');
          }}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-1 text-ink-subtle transition-colors hover:text-ink focus-ring"
        >
          <X size={12} aria-hidden />
        </button>
      )}
    </div>
  );
}
