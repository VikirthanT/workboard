import { useState } from 'react';
import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import { PageLoading } from '../../app/components/PageLoading';
import { Alert } from '../../app/components/ui/alert';
import { Button } from '../../app/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../app/components/ui/table';
import { formatDateTime } from '../../app/lib/format';
import { errorMessage } from '../../services/api';
import { describeAudit, pageRange } from './auditText';
import { useAudit } from './hooks';

/** Every team and access change, newest first, fifty at a time. Read-only: the database refuses edits and deletes. */
export function AuditLog() {
  const [page, setPage] = useState(0);
  const audit = useAudit(page);

  if (audit.isError) return <Alert variant="danger" title="Could not load the audit log">{errorMessage(audit.error)}</Alert>;
  if (!audit.data) return <PageLoading label="Loading the audit log…" />;
  const { items, total, offset } = audit.data;
  const last = offset + items.length >= total;

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-raised">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <tr><TableHead>When</TableHead><TableHead>Who</TableHead><TableHead>Change</TableHead><TableHead>Reason</TableHead></tr>
          </TableHeader>
          <TableBody>
            {items.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="tabular-nums">{formatDateTime(e.createdAt)}</TableCell>
                <TableCell>{e.actorName ?? 'System'}</TableCell>
                <TableCell className="whitespace-normal font-medium text-ink">{describeAudit(e)}</TableCell>
                <TableCell className="whitespace-normal">{e.reason ?? <span className="text-ink-subtle">No reason given</span>}</TableCell>
              </TableRow>
            ))}
            {items.length === 0 && <TableRow><TableCell colSpan={4} className="py-10 text-center text-ink-subtle">No changes yet.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between border-t border-line px-5 py-3">
        <span className="text-sm text-ink-subtle">{pageRange(offset, items.length, total)}</span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}><CaretLeft size={14} aria-hidden />Newer</Button>
          <Button variant="outline" size="sm" disabled={last} onClick={() => setPage((p) => p + 1)}>Older<CaretRight size={14} aria-hidden /></Button>
        </div>
      </div>
    </div>
  );
}
