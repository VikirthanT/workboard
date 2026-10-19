import type { Session } from '../app/types/types';

const KEY = 'wb_session';

export function getSession(): Session | null {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || 'null');
  } catch {
    return null;
  }
}
/** The board's remembered view (`useBoardParams`) belongs to whoever was signed in, so it goes with the session. */
function clearBoardViews() {
  Object.keys(sessionStorage).filter((k) => k.startsWith('wb_board:')).forEach((k) => sessionStorage.removeItem(k));
}
export function saveSession(s: Session) {
  try { clearBoardViews(); sessionStorage.setItem(KEY, JSON.stringify(s)); } catch { /* storage unavailable */ }
}
export function clearSession() {
  try { clearBoardViews(); sessionStorage.removeItem(KEY); } catch { /* ignore */ }
}
