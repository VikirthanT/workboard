import type { Me, Session } from '../app/types/types';
import type { WireBoard, WireDevAccount, WireIdentity, WireSession } from './backendTypes';
import { apiClient } from './axiosInstance';
import { mapRealMe, runsTeam } from './mappers';

/** One line of the dev account list; `note` explains an account the server will refuse. */
export interface DevAccount { email: string; name: string; note?: string }

/** Step 2 of the Google flow: trade the callback `code` for a session (Mdm Duro pattern). Built last, on the server too. */
export async function exchangeGoogleCode(code: string): Promise<Session> {
  const { data } = await apiClient.get<WireSession>('/auth/google/exchange', { params: { code } });
  return data;
}

/** Dev builds only: the accounts the login page offers instead of Google (the server serves them with DEV_AUTH on). */
export async function getDevAccounts(): Promise<DevAccount[]> {
  if (!import.meta.env.DEV) throw new Error('Not available'); // lets a production build drop the rest
  const { data } = await apiClient.get<WireDevAccount[]>('/dev/accounts');
  return data.map((a) => ({ email: a.email, name: a.name, note: a.can_sign_in ? undefined : 'Not a manager or admin: sign-in is refused' }));
}

/**
 * Dev builds only: the server's DEV_AUTH stub names the caller by an email header (it checks that person may sign
 * in: an active manager or admin). Not Google sign-in, which is built last.
 */
export async function devSignIn(email: string): Promise<Session> {
  if (!import.meta.env.DEV) throw new Error('Not available'); // lets a production build drop the rest
  const { data } = await apiClient.get<WireIdentity>('/me', { headers: { 'X-Dev-User-Email': email.trim().toLowerCase() } });
  return { token: '', email: data.email, name: data.name }; // no token: the dev header names the caller
}

/** Who is signed in, their team's people and the header count, built from three real endpoints. */
export async function getMe(): Promise<Me> {
  const { data: self } = await apiClient.get<WireIdentity>('/me');
  if (!runsTeam(self)) return mapRealMe(self, [], null);
  const [members, board] = await Promise.all([
    apiClient.get<WireIdentity[]>(`/teams/${self.team_id}/members`),
    apiClient.get<WireBoard>('/board'),
  ]);
  return mapRealMe(self, members.data, board.data);
}
