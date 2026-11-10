import { useMemo, useState } from 'react';
import { DndContext, DragOverlay, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent, type DragStartEvent } from '@dnd-kit/core';
import { Badge } from '../../../app/components/ui/badge';
import { Button } from '../../../app/components/ui/button';
import { cn } from '../../../app/lib/utils';
import { BOARD_PAGE, STATUSES, STATUS_LABEL, type ColumnSizes, type Status, type Task, type Transition } from '../../../app/types/types';
import { TaskCard } from './TaskCard';

interface Props {
  tasks: Task[];
  onOpen: (id: string) => void;
  /** Called with the transition the drop means; the board decides about reason dialogs. */
  onTransition: (task: Task, tr: Transition) => void;
  onBlockedDrop: (task: Task, to: Status) => void;
  /** A read-only view (an admin on a team they do not run): cards open but cannot be dragged. */
  readOnly?: boolean;
  /** Each column's full count (the server sends only the first cards of each). */
  columnTotals: Record<Status, number>;
  /** Columns grown by "Load more", and how to grow or reset one. */
  sizes: ColumnSizes;
  onSizesChange: (sizes: ColumnSizes) => void;
}

function DraggableCard({ task, onOpen, readOnly }: { task: Task; onOpen: (id: string) => void; readOnly: boolean }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: task.id, disabled: readOnly });
  return (
    <TaskCard
      ref={setNodeRef}
      task={task}
      dragging={isDragging}
      onClick={() => onOpen(task.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(task.id);
        }
      }}
      /* Read-only cards are plain buttons: no drag handlers, and no "disabled / draggable" ARIA from dnd-kit. */
      {...(readOnly ? {} : attributes)}
      {...(readOnly ? {} : listeners)}
      /* dnd-kit's attributes set role/tabIndex; keep ours for the button semantics. */
      role="button"
      tabIndex={0}
    />
  );
}

interface ColumnProps {
  status: Status;
  tasks: Task[];
  total: number;
  onOpen: (id: string) => void;
  onLoadMore: () => void;
  onShowLess?: () => void;
  droppable: boolean;
  dragging: boolean;
  readOnly: boolean;
}

function Column({ status, tasks, total, onOpen, onLoadMore, onShowLess, droppable, dragging, readOnly }: ColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const left = total - tasks.length;
  return (
    <section
      aria-labelledby={`col-${status}`}
      className={cn(
        'flex min-w-[248px] flex-1 flex-col rounded-lg border border-line bg-surface-subtle transition-colors',
        dragging && droppable && 'border-brand-border bg-brand-subtle',
        dragging && !droppable && 'opacity-60',
        isOver && droppable && 'border-brand',
      )}
    >
      <header className="flex items-center justify-between px-3 py-2.5">
        <h2 id={`col-${status}`} className="text-base font-semibold text-ink">{STATUS_LABEL[status]}</h2>
        <Badge>{total}</Badge>
      </header>
      <div ref={setNodeRef} className="flex min-h-[120px] flex-1 flex-col gap-2 px-2 pb-2">
        {tasks.map((t) => <DraggableCard key={t.id} task={t} onOpen={onOpen} readOnly={readOnly} />)}
        {tasks.length === 0 && <p className="px-1 py-6 text-center text-sm text-ink-subtle">Nothing here</p>}
        {left > 0 && (
          <Button variant="ghost" size="sm" onClick={onLoadMore}>
            Load {Math.min(left, BOARD_PAGE)} more <span className="text-ink-subtle">({left} left)</span>
          </Button>
        )}
        {onShowLess && <Button variant="ghost" size="sm" onClick={onShowLess}>Show less</Button>}
      </div>
    </section>
  );
}

export function KanbanBoard({ tasks, onOpen, onTransition, onBlockedDrop, readOnly = false, columnTotals, sizes, onSizesChange }: Props) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const [activeId, setActiveId] = useState<string | null>(null);

  // The server sends each column already sorted (open: most urgent first; Done: newest closed first).
  const byStatus = useMemo(() => {
    const m = new Map<Status, Task[]>(STATUSES.map((s) => [s, []]));
    tasks.forEach((t) => m.get(t.status)!.push(t));
    return m;
  }, [tasks]);

  function showLess(status: Status) {
    const { [status]: _dropped, ...rest } = sizes;
    onSizesChange(rest);
  }

  const active = tasks.find((t) => t.id === activeId) ?? null;
  const validTargets = new Set(active?.actions.transitions.map((t) => t.to));

  function end(e: DragEndEvent) {
    setActiveId(null);
    const task = tasks.find((t) => t.id === e.active.id);
    const to = e.over?.id as Status | undefined;
    if (!task || !to || to === task.status) return;
    const tr = task.actions.transitions.find((t) => t.to === to);
    if (tr) onTransition(task, tr);
    else onBlockedDrop(task, to);
  }

  return (
    <DndContext sensors={sensors} onDragStart={(e: DragStartEvent) => setActiveId(String(e.active.id))} onDragEnd={end} onDragCancel={() => setActiveId(null)}>
      <div className="flex gap-3 overflow-x-auto pb-3">
        {STATUSES.map((s) => (
          <Column
            key={s}
            status={s}
            tasks={byStatus.get(s)!}
            total={columnTotals[s]}
            onOpen={onOpen}
            onLoadMore={() => onSizesChange({ ...sizes, [s]: (sizes[s] ?? BOARD_PAGE) + BOARD_PAGE })}
            onShowLess={sizes[s] ? () => showLess(s) : undefined}
            droppable={validTargets.has(s)}
            dragging={!!active}
            readOnly={readOnly}
          />
        ))}
      </div>
      <DragOverlay>{active ? <TaskCard task={active} className="rotate-1 shadow-overlay" /> : null}</DragOverlay>
    </DndContext>
  );
}
