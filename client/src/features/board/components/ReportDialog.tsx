import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { DownloadSimple, FilePdf } from '@phosphor-icons/react';
import { Button } from '../../../app/components/ui/button';
import { DatePicker } from '../../../app/components/ui/date-picker';
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../../app/components/ui/dialog';
import { Label } from '../../../app/components/ui/label';
import { FilterTabsList, FilterTabsTrigger, Tabs } from '../../../app/components/ui/tabs';
import { monthRange, quarterRange, todayISO, weekRange } from '../../../app/domain/dates';
import { formatDay } from '../../../app/lib/format';
import type { BoardQuery } from '../../../app/types/types';
import { errorMessage } from '../../../services/api';
import { useAllTeamsReport, useTeamReport } from '../hooks';
import { downloadSheetAsPdf } from '../pdf';
import { PLAIN_DIGITS, PrintSection, PrintTeams, Section, TeamsTable, allTeamsSections, teamSections, toCsv } from './ReportTables';
import { SummaryTiles } from './ReportVisuals';

const PRESETS = { week: weekRange, month: monthRange, quarter: quarterRange } as const;
type Preset = keyof typeof PRESETS | 'custom' | 'all';

const longDate = (iso: string) => `${formatDay(iso)} ${iso.slice(0, 4)}`;

interface Props {
  open: boolean;
  query: BoardQuery;
  /** Admins can switch the report from the team in view to every team at once. */
  canAllTeams?: boolean;
  onClose: () => void;
}

/**
 * Task numbers for everything ever and for a chosen period, as a preview, a CSV, or a printed / saved PDF.
 * Two scopes: the people in the board's current view, or (admins) every team, one collapsible group per team.
 */
export function ReportDialog({ open, query, canAllTeams = false, onClose }: Props) {
  const [preset, setPreset] = useState<Preset>('week');
  const [range, setRange] = useState(() => weekRange(todayISO()));
  const [everyTeam, setEveryTeam] = useState(false);
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  const teamReport = useTeamReport(query, range.from, range.to, open && !everyTeam);
  const allReport = useAllTeamsReport(range.from, range.to, open && everyTeam && canAllTeams);
  const report = everyTeam ? allReport : teamReport;
  const sheetRef = useRef<HTMLDivElement>(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  function choose(p: Preset) {
    setPreset(p);
    if (p !== 'custom' && p !== 'all') setRange(PRESETS[p](todayISO()));
  }

  function toggleTeam(id: string) {
    setExpanded((now) => {
      const next = new Set(now);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  // One section only: the chosen period, or all time when that tab is picked.
  const isAll = preset === 'all';
  const heading = isAll ? 'All time' : `${longDate(range.from)} to ${longDate(range.to)}`;
  const subtitle = isAll ? 'Every task, no date limit' : 'Selected period';
  const teamBlock = teamReport.data && (isAll ? teamReport.data.allTime : teamReport.data.period);
  const teamsBlock = allReport.data && (isAll ? allReport.data.allTime : allReport.data.period);
  const totals = everyTeam ? teamsBlock?.totals : teamBlock?.totals;
  const ready = everyTeam ? !!teamsBlock : !!teamBlock;

  const reportName = everyTeam ? 'All teams report' : 'Team report';
  const fileStem = `${everyTeam ? 'all-teams' : 'team'}-report-${isAll ? 'all-time' : `${range.from}-to-${range.to}`}`;

  async function downloadPdf() {
    if (!sheetRef.current) return;
    setPdfBusy(true);
    setPdfError(null);
    try {
      await downloadSheetAsPdf(sheetRef.current, `${fileStem}.pdf`);
    } catch {
      setPdfError('Could not create the PDF. Try again, or use the CSV.');
    } finally {
      setPdfBusy(false);
    }
  }

  function downloadCsv() {
    const sections = everyTeam ? (teamsBlock ? allTeamsSections(heading, teamsBlock) : []) : (teamBlock ? teamSections(heading, teamBlock) : []);
    const url = URL.createObjectURL(new Blob([toCsv(sections)], { type: 'text/csv;charset=utf-8' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: `${fileStem}.csv` });
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="max-w-[1100px]">
          <DialogHeader>
            <div>
              <DialogTitle>{reportName}</DialogTitle>
              <DialogDescription>
                {everyTeam
                  ? 'Task numbers for every team, one group per team: open a team to see its people. All time, and for the period you pick.'
                  : 'Task numbers for the people in your current view: all time, and for the period you pick.'}
              </DialogDescription>
            </div>
          </DialogHeader>
          <DialogBody className="flex flex-col gap-4">
            <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
              {canAllTeams && (
                <Tabs value={everyTeam ? 'all' : 'team'} onValueChange={(v) => setEveryTeam(v === 'all')}>
                  <FilterTabsList aria-label="Scope">
                    <FilterTabsTrigger value="team">This team</FilterTabsTrigger>
                    <FilterTabsTrigger value="all">All teams</FilterTabsTrigger>
                  </FilterTabsList>
                </Tabs>
              )}
              <Tabs value={preset} onValueChange={(v) => choose(v as Preset)}>
                <FilterTabsList aria-label="Period">
                  <FilterTabsTrigger value="week">Weekly</FilterTabsTrigger>
                  <FilterTabsTrigger value="month">Monthly</FilterTabsTrigger>
                  <FilterTabsTrigger value="quarter">Quarterly</FilterTabsTrigger>
                  <FilterTabsTrigger value="custom">Custom</FilterTabsTrigger>
                  <FilterTabsTrigger value="all">All time</FilterTabsTrigger>
                </FilterTabsList>
              </Tabs>
              {!isAll && (
                <>
                  <div className="w-[170px]">
                    <Label htmlFor="rep-from">From</Label>
                    <DatePicker id="rep-from" value={range.from} maxDate={range.to} onChange={(v) => (setPreset('custom'), v && setRange({ ...range, from: v }))} />
                  </div>
                  <div className="w-[170px]">
                    <Label htmlFor="rep-to">To</Label>
                    <DatePicker id="rep-to" value={range.to} minDate={range.from} onChange={(v) => (setPreset('custom'), v && setRange({ ...range, to: v }))} />
                  </div>
                </>
              )}
            </div>
            {report.isError && <p role="alert" className="text-base text-danger-ink">{errorMessage(report.error, 'Could not load the report.')}</p>}
            {pdfError && <p role="alert" className="text-base text-danger-ink">{pdfError}</p>}
            {report.isPending && !report.isError && <p className="text-base text-ink-subtle">Loading report…</p>}
            {totals && <SummaryTiles totals={totals} />}
            {everyTeam && teamsBlock && (
              <>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setExpanded(new Set(teamsBlock.teams.map((t) => t.team.id)))}>Expand all</Button>
                  <Button variant="ghost" size="sm" onClick={() => setExpanded(new Set())}>Collapse all</Button>
                </div>
                <TeamsTable title={heading} block={teamsBlock} expanded={expanded} onToggle={toggleTeam} />
              </>
            )}
            {!everyTeam && teamBlock && <Section title={heading} block={teamBlock} />}
            <p className="text-sm text-ink-subtle">
              {isAll
                ? (everyTeam ? 'Every task ever assigned, in every team.' : 'Every task ever assigned to these people.')
                : 'Open work (To Do to Overdue) is the current state. Assigned means created in the period, Done means closed in it, so Completion can pass 100%.'}
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={onClose}>Close</Button>
            <Button variant="outline" disabled={!ready} onClick={downloadCsv}><DownloadSimple size={14} aria-hidden />CSV</Button>
            <Button disabled={!ready || pdfBusy} onClick={downloadPdf}><FilePdf size={14} aria-hidden />{pdfBusy ? 'Creating…' : 'PDF'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {open && ready && totals && createPortal(
        // Kept off-screen at a fixed width (not display:none) so it can be drawn into the PDF.
        // A printed page cannot be opened, so every team is laid out in full here.
        <div ref={sheetRef} aria-hidden style={{ position: 'fixed', left: -10000, top: 0, width: 1100 }} className={`flex flex-col gap-6 bg-surface p-8 text-ink ${PLAIN_DIGITS}`}>
          <header data-pdf-block className="border-b border-line pb-4">
            <h1 className="font-display text-xl font-semibold">{reportName} ({heading})</h1>
            <p className="mt-1 text-base text-ink-muted">Work Board · generated {longDate(todayISO())}</p>
          </header>
          <SummaryTiles totals={totals} />
          {everyTeam && teamsBlock && (
            <>
              <PrintTeams title={heading} subtitle={subtitle} block={teamsBlock} />
              <TeamsTable title={`Summary table: ${heading}`} block={teamsBlock} expanded={new Set(teamsBlock.teams.map((t) => t.team.id))} onToggle={() => {}} compact />
            </>
          )}
          {!everyTeam && teamBlock && (
            <>
              <PrintSection title={heading} subtitle={subtitle} block={teamBlock} />
              <Section title={`Summary table: ${heading}`} block={teamBlock} compact />
            </>
          )}
        </div>,
        document.body,
      )}
    </>
  );
}
