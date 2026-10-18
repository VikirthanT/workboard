import { useMutation, useQueryClient } from '@tanstack/react-query';
import { devSignIn, exchangeGoogleCode, saveSession, clearSession } from '../../../services/api';
import type { Session } from '../../../app/types/types';

/** Replace the session and drop every cached query: the new user sees different data. */
function useStartSession() {
  const qc = useQueryClient();
  return async (s: Session) => {
    saveSession(s);
    await qc.cancelQueries();
    qc.clear();
  };
}

export function useDevSignIn() {
  const start = useStartSession();
  return useMutation({ mutationFn: devSignIn, onSuccess: start });
}

export function useGoogleExchange() {
  const start = useStartSession();
  return useMutation({ mutationFn: exchangeGoogleCode, onSuccess: start });
}

export function useSignOut() {
  const qc = useQueryClient();
  return () => {
    clearSession();
    qc.clear();
  };
}
