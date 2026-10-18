import { useQuery } from '@tanstack/react-query';
import { ME_KEY } from '../app/constants/queryKeys';
import { getMe, getSession } from '../services/api';

/** Who is signed in, plus derived manager/admin flags, assignable people and header counts. */
export function useCurrentUser() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: getMe,
    enabled: !!getSession(),
    staleTime: 15_000,
  });
}
