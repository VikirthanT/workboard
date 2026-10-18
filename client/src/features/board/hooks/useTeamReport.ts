import { useQuery } from '@tanstack/react-query';
import { getAllTeamsReportKey, getReportKey } from '../../../app/constants/queryKeys';
import type { BoardQuery } from '../../../app/types/types';
import { getAllTeamsReport, getTeamReport } from '../../../services/api';

export function useTeamReport(query: BoardQuery, from: string, to: string, enabled: boolean) {
  return useQuery({
    queryKey: getReportKey(query, from, to),
    queryFn: () => getTeamReport(query, from, to),
    enabled: enabled && !!from && !!to && from <= to,
  });
}

/** The admin's report across every team. */
export function useAllTeamsReport(from: string, to: string, enabled: boolean) {
  return useQuery({
    queryKey: getAllTeamsReportKey(from, to),
    queryFn: () => getAllTeamsReport(from, to),
    enabled: enabled && !!from && !!to && from <= to,
  });
}
