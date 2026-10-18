import type { AllTeamsReport, BoardQuery, TeamReport } from '../app/types/types';
import type { WireAllTeamsReport, WireTeamReport } from './backendTypes';
import { apiClient } from './axiosInstance';
import { mapAllTeamsReport, mapTeamReport } from './mappers';

/** Report for the people in the board's current view (the team, or one person), over From..To. */
export async function getTeamReport(q: BoardQuery, from: string, to: string): Promise<TeamReport> {
  const { data } = await apiClient.get<WireTeamReport>('/reports/team', {
    params: { team: q.teamId ?? undefined, person: q.personId ?? undefined, from, to },
  });
  return mapTeamReport(data);
}

/** Admins only: every team in one report, each with its own people, over From..To. */
export async function getAllTeamsReport(from: string, to: string): Promise<AllTeamsReport> {
  const { data } = await apiClient.get<WireAllTeamsReport>('/reports/all-teams', { params: { from, to } });
  return mapAllTeamsReport(data);
}
