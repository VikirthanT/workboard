import { useQuery } from '@tanstack/react-query';
import { getDevAccounts } from '../../../services/api';

/** Dev only: the accounts the login page offers in place of Google (served by the server while DEV_AUTH is on). */
export function useDevAccounts(enabled: boolean) {
  return useQuery({ queryKey: ['dev-accounts'], queryFn: getDevAccounts, enabled });
}
