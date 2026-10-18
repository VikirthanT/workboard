/* The report's tables and print layouts. ReportDialog decides what to show; this file draws it.
   Two shapes: one team (a row per person) and every team (a collapsible group per team, a row per person inside). */
import type { ReactNode } from 'react';
import { CaretDown, CaretRight } from '@phosphor-icons/react';
import { Badge } from '../../../app/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../app/components/ui/table';
import type { ReportCounts } from '../../../app/domain/report';
import type { ReportBlock, TeamRow, TeamsBlock } from '../../../app/types/types';
import { ReportValue } from './ReportVisuals';

const pct = (n: number | null) => (n === null ? '–' : `${Math.round(n * 100)}%`);

export const COLUMNS: [string, (c: ReportCounts) => string][] = [
  ['To Do', (c) => String(c.todo)],
  ['In Progress', (c) => String(c.inProgress)],
  ['Blocked', (c) => String(c.blocked)],
  ['In Review', (c) => String(c.review)],
  ['Overdue', (c) => String(c.overdue)],
  ['Assigned', (c) => String(c.assigned)],
  ['Done', (c) => String(c.done)],
  ['Completion', (c) => pct(c.completionRate)],
  ['On time', (c) => pct(c.onTimeRate)],
  ['Returned', (c) => String(c.returned)],
];

export const TEAM_TOTAL = 'Team total';
export const ALL_TEAMS_TOTAL = 'All teams total';

/* The app sets tabular figures everywhere, which gives a "1" a full-width slot ("1 2 Oct"). Dates and the PDF read better without. */
export const PLAIN_DIGITS = 'proportional-nums [font-feature-settings:normal]';

const peopleCount = (n: number) => `${n} ${n === 1 ? 'person' : 'people'}`;
const teamLabel = (row: TeamRow) => `${row.team.name} (${row.team.manager?.displayName ?? 'No manager'})`;

// ---- CSV ----

export interface CsvSection {
  title: string;
  head: string; // the first column's heading: "Team members" or "Teams"
  totalLabel: string;
  totals: ReportCounts;
  rows: { name: string; counts: ReportCounts }[];
}

export function toCsv(sections: CsvSection[]) {
  const cell = (s: string) => `"${s.replaceAll('"', '""')}"`;
  const row = (name: string, c: ReportCounts) => [name, ...COLUMNS.map(([, f]) => f(c))];
  return sections
    .flatMap((s) => [[s.title], [s.head, ...COLUMNS.map(([h]) => h)], row(s.totalLabel, s.totals), ...s.rows.map((r) => row(r.name, r.counts)), []])
    .map((r) => r.map(cell).join(','))
    .join('\r\n');
}

/** The sections of a one-team report. */
export const teamSections = (title: string, block: ReportBlock): CsvSection[] => [
  { title, head: 'Team members', totalLabel: TEAM_TOTAL, totals: block.totals, rows: block.people.map((p) => ({ name: p.person.displayName, counts: p.counts })) },
];

/** The all-teams overview first, then one section per team with its people. */
export const allTeamsSections = (title: string, block: TeamsBlock): CsvSection[] => [
  { title: `${title} (all teams)`, head: 'Teams', totalLabel: ALL_TEAMS_TOTAL, totals: block.totals, rows: block.teams.map((t) => ({ name: teamLabel(t), counts: t.counts })) },
  ...block.teams.map((t) => ({
    title: `${teamLabel(t)}: ${title}`, head: 'Team members', totalLabel: TEAM_TOTAL, totals: t.counts,
    rows: t.people.map((p) => ({ name: p.person.displayName, counts: p.counts })),
  })),
];

// ---- on-screen tables ----

type RowKind = 'total' | 'subtotal' | 'person';

function ValueRow({ label, counts, kind }: { label: ReactNode; counts: ReportCounts; kind: RowKind }) {
  return (
    <TableRow className={kind === 'person' ? undefined : 'bg-surface-subtle'}>
      <TableCell className={kind === 'person' ? undefined : 'font-medium text-ink'}>{label}</TableCell>
      {COLUMNS.map(([h, f]) => (
        <TableCell key={h} className={`text-right ${kind === 'person' ? 'font-medium' : 'font-semibold'}`}>
          <ReportValue label={h} counts={counts} text={f(counts)} />
        </TableCell>
      ))}
    </TableRow>
  );
}

function TableFrame({ head, compact, children }: { head: string; compact?: boolean; children: ReactNode }) {
  // compact (print): tighter cells so every column fits the page instead of being cut off.
  return (
    <div className={compact ? 'rounded-lg border border-line [&_td]:px-2 [&_td]:text-sm [&_th]:px-2 [&_th]:text-sm' : 'overflow-x-auto rounded-lg border border-line'}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">{head}</TableHead>
            {COLUMNS.map(([h]) => <TableHead key={h} className="whitespace-nowrap text-right">{h}</TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>{children}</TableBody>
      </Table>
    </div>
  );
}

/** One team: the team total, then a row per person. */
export function Section({ title, block, compact }: { title: string; block: ReportBlock; compact?: boolean }) {
  return (
    <section data-pdf-block className="break-inside-avoid">
      <h3 className={`mb-2 font-display text-md font-semibold text-ink ${PLAIN_DIGITS}`}>{title}</h3>
      <TableFrame head="Team members" compact={compact}>
        <ValueRow label={TEAM_TOTAL} counts={block.totals} kind="total" />
        {block.people.map((p) => <ValueRow key={p.person.id} label={p.person.displayName} counts={p.counts} kind="person" />)}
      </TableFrame>
    </section>
  );
}

/**
 * Every team: the grand total, then one group per team. A group is a row you can open (the chevron, or the
 * whole name) to see the people under it; closed, it still shows the team's own numbers.
 */
export function TeamsTable({
  title, block, expanded, onToggle, compact,
}: { title: string; block: TeamsBlock; expanded: ReadonlySet<string>; onToggle: (teamId: string) => void; compact?: boolean }) {
  return (
    <section data-pdf-block className="break-inside-avoid">
      <h3 className={`mb-2 font-display text-md font-semibold text-ink ${PLAIN_DIGITS}`}>{title}</h3>
      <TableFrame head="Teams" compact={compact}>
        <ValueRow label={ALL_TEAMS_TOTAL} counts={block.totals} kind="total" />
        {block.teams.map((row) => {
          const open = expanded.has(row.team.id);
          return (
            <TeamGroup key={row.team.id} row={row} open={open} onToggle={() => onToggle(row.team.id)} />
          );
        })}
      </TableFrame>
    </section>
  );
}

function TeamGroup({ row, open, onToggle }: { row: TeamRow; open: boolean; onToggle: () => void }) {
  const Chevron = open ? CaretDown : CaretRight;
  return (
    <>
      <ValueRow
        kind="subtotal"
        counts={row.counts}
        label={
          <button
            type="button"
            aria-expanded={open}
            onClick={onToggle}
            className="flex w-full items-center gap-2 rounded-md text-left font-medium text-ink focus-ring"
          >
            <Chevron size={14} aria-hidden className="shrink-0 text-ink-subtle" />
            <span>{teamLabel(row)}</span>
            <Badge>{row.people.length}</Badge>
          </button>
        }
      />
      {open && row.people.map((p) => (
        <ValueRow key={p.person.id} kind="person" counts={p.counts} label={<span className="block pl-7">{p.person.displayName}</span>} />
      ))}
      {open && row.people.length === 0 && (
        <TableRow>
          <TableCell colSpan={COLUMNS.length + 1} className="pl-9 text-sm text-ink-subtle">No tasks assigned on this team.</TableCell>
        </TableRow>
      )}
    </>
  );
}

// ---- print layouts (the PDF) ----

/* Name on the left, then the counts as equal cells in two rows of five (open work, then results),
   each cell carrying its own label so a label can never drift from its number. */
function PersonRow({ name, note, counts, strong }: { name: string; note?: string; counts: ReportCounts; strong?: boolean }) {
  return (
    <article data-pdf-block className={`flex break-inside-avoid flex-col gap-3 rounded-lg border px-4 py-3 ${strong ? 'border-line-strong bg-surface-subtle' : 'border-line'}`}>
      <div className="flex items-center gap-4">
        <div className="w-[200px] shrink-0">
          <h3 className="truncate font-display text-md font-semibold text-ink">{name}</h3>
          {note && <p className="truncate text-sm text-ink-muted">{note}</p>}
        </div>
        <dl className="grid min-w-0 flex-1 grid-cols-5 gap-x-2 gap-y-2">
          {COLUMNS.map(([h, f]) => (
            <div key={h} className="text-center">
              <dt className="whitespace-nowrap text-sm text-ink-muted">{h}</dt>
              <dd className="font-display text-lg font-semibold"><ReportValue label={h} counts={counts} text={f(counts)} /></dd>
            </div>
          ))}
        </dl>
      </div>
    </article>
  );
}

function PrintHeading({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div data-pdf-block className="mb-1">
      <h2 className="font-display text-lg font-semibold text-ink">{title}</h2>
      <p className="text-base text-ink-muted">{subtitle}</p>
    </div>
  );
}

/** The PDF layout for one team: a titled section, one box per person, then the team total. */
export function PrintSection({ title, subtitle, block }: { title: string; subtitle: string; block: ReportBlock }) {
  return (
    <section className="flex flex-col gap-2">
      <PrintHeading title={title} subtitle={subtitle} />
      {block.people.map((p) => <PersonRow key={p.person.id} name={p.person.displayName} note={p.person.email} counts={p.counts} />)}
      <PersonRow name={TEAM_TOTAL} note={peopleCount(block.people.length)} counts={block.totals} strong />
    </section>
  );
}

/** The PDF layout for every team: each team in full (a printed page cannot be opened), then the grand total. */
export function PrintTeams({ title, subtitle, block }: { title: string; subtitle: string; block: TeamsBlock }) {
  return (
    <div className="flex flex-col gap-6">
      {block.teams.map((row) => (
        <PrintSection key={row.team.id} title={`${teamLabel(row)}: ${title}`} subtitle={subtitle} block={{ totals: row.counts, people: row.people }} />
      ))}
      <section className="flex flex-col gap-2">
        <PersonRow name={ALL_TEAMS_TOTAL} note={`${block.teams.length} ${block.teams.length === 1 ? 'team' : 'teams'}`} counts={block.totals} strong />
      </section>
    </div>
  );
}
