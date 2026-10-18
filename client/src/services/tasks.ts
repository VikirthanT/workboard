import type { ActivityItem, Board, BoardQuery, Task, TaskDetail, TaskInput, Status } from '../app/types/types';
import type { WireActivity, WireBoard, WireTask, WireTaskDetail } from './backendTypes';
import { apiClient } from './axiosInstance';
import { mapActivity, mapBoardTeam, mapSummary, mapTask } from './mappers';

export async function getBoard(q: BoardQuery): Promise<Board> {
  const { data } = await apiClient.get<WireBoard>('/board', {
    params: {
      team: q.teamId ?? undefined,
      attention: q.attention || undefined,
      person: q.personId ?? undefined,
      filter: q.filters.join(',') || undefined,
    },
  });
  return {
    team: mapBoardTeam(data.team),
    readOnly: data.read_only,
    tasks: data.tasks.map(mapTask),
    people: data.people.map(mapSummary),
    filterCounts: data.filter_counts as Board['filterCounts'],
    attentionCount: data.attention_count,
    stats: data.stats,
    orphans: data.orphans.map(mapTask),
  };
}

export async function getTask(id: string): Promise<TaskDetail> {
  const { data } = await apiClient.get<WireTaskDetail>(`/tasks/${id}`);
  return { task: mapTask(data.task), timeline: data.timeline.map(mapActivity) };
}

const toWireInput = (i: Partial<TaskInput>) => ({
  title: i.title,
  description: i.description,
  priority: i.priority,
  due_at: i.dueAt,
  assignee_id: i.assigneeId,
});

export async function createTask(input: TaskInput): Promise<Task> {
  const { data } = await apiClient.post<WireTask>('/tasks', toWireInput(input));
  return mapTask(data);
}

export async function updateTask(id: string, patch: Partial<TaskInput>): Promise<Task> {
  const { data } = await apiClient.patch<WireTask>(`/tasks/${id}`, toWireInput(patch));
  return mapTask(data);
}

export async function deleteTask(id: string) {
  await apiClient.delete(`/tasks/${id}`);
}

/** `completedOn` ("YYYY-MM-DD") is only for a move to Done: the day the work really finished. */
export async function moveTask(id: string, to: Status, note?: string, completedOn?: string): Promise<Task> {
  const { data } = await apiClient.post<WireTask>(`/tasks/${id}/status`, { to, note, completed_on: completedOn });
  return mapTask(data);
}

export async function addComment(id: string, body: string): Promise<ActivityItem> {
  const { data } = await apiClient.post<WireActivity>(`/tasks/${id}/comments`, { body });
  return mapActivity(data);
}
