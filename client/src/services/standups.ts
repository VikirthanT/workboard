import type { ChannelName, StandupChannel, Suggestion, SuggestionPatch, SuggestionsPage } from '../app/types/types';
import type { WireChannelName, WireStandupChannel, WireSuggestion, WireSuggestionsPage } from './backendTypes';
import { apiClient } from './axiosInstance';
import { mapStandupChannel, mapSuggestion, mapSuggestionsPage } from './mappers';

/** Every channel in the standup app, by name, for an admin's channel picker. The server answers 501 when it has no standup database. */
export async function getStandupChannels(): Promise<StandupChannel[]> {
  const { data } = await apiClient.get<WireStandupChannel[]>('/standups/channels');
  return data.map(mapStandupChannel);
}

/** The name of a channel id (the standup app's list first, then Slack). The error says when it cannot be found. */
export async function getChannelName(channelId: string): Promise<ChannelName> {
  const { data } = await apiClient.get<WireChannelName>(`/standups/channels/${encodeURIComponent(channelId)}`);
  return data;
}

/** Each person on the team with their latest standup and suggestions. The team's manager, or an admin (read only). */
export async function getSuggestions(teamId: string): Promise<SuggestionsPage> {
  const { data } = await apiClient.get<WireSuggestionsPage>(`/teams/${teamId}/suggestions`);
  return mapSuggestionsPage(data);
}

/**
 * Read the team's standup channel and propose tasks. Runs the language model, so it can take a while. With `personId`
 * only that person's posts are read, so a manager can go one person at a time. Returns the page.
 */
export async function syncSuggestions(p: { teamId: string; personId?: string }): Promise<SuggestionsPage> {
  const url = `/teams/${p.teamId}/suggestions/sync`;
  const { data } = p.personId
    ? await apiClient.post<WireSuggestionsPage>(url, undefined, { params: { person_id: p.personId } })
    : await apiClient.post<WireSuggestionsPage>(url);
  return mapSuggestionsPage(data);
}

/**
 * Create a task from each chosen pending suggestion, assigned to the person it is for. All or nothing. Returns the page.
 * A task needs a due date: `dueDates` (by suggestion id, "YYYY-MM-DD") gives the ones a suggestion lacks, or changes one.
 */
export async function addSuggestions(p: { teamId: string; suggestionIds: string[]; dueDates?: Record<string, string> }): Promise<SuggestionsPage> {
  const { data } = await apiClient.post<WireSuggestionsPage>(`/teams/${p.teamId}/suggestions/add`, {
    suggestion_ids: p.suggestionIds,
    due_dates: p.dueDates && Object.keys(p.dueDates).length > 0 ? p.dueDates : undefined,
  });
  return mapSuggestionsPage(data);
}

/** Only the fields present are sent, so an absent one is left alone and a null date clears it. */
export async function editSuggestion(p: { id: string; patch: SuggestionPatch }): Promise<Suggestion> {
  const { title, description, priority, personId, startAt, dueAt } = p.patch;
  const body = { title, description, priority, person_id: personId, start_at: startAt, due_at: dueAt };
  const { data } = await apiClient.patch<WireSuggestion>(`/suggestions/${p.id}`, body);
  return mapSuggestion(data);
}

/** A rejected suggestion stays visible, and restorable, for 3 days. */
export async function rejectSuggestion(id: string): Promise<Suggestion> {
  const { data } = await apiClient.post<WireSuggestion>(`/suggestions/${id}/reject`);
  return mapSuggestion(data);
}

export async function restoreSuggestion(id: string): Promise<Suggestion> {
  const { data } = await apiClient.post<WireSuggestion>(`/suggestions/${id}/restore`);
  return mapSuggestion(data);
}
