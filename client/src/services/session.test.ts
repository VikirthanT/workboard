import { beforeEach, describe, expect, it } from 'vitest';
import { clearSession, getSession, saveSession } from './session';

const who = { token: 't', email: 'a@atimotors.com', name: 'A' };

beforeEach(() => {
  sessionStorage.clear();
  sessionStorage.setItem('wb_board:own', '{"taskId":"x"}');
  sessionStorage.setItem('wb_board:npi-id', '{}');
});

describe('session and the remembered board view', () => {
  it('signing out drops every team’s view', () => {
    saveSession(who);
    sessionStorage.setItem('wb_board:own', '{}');
    clearSession();
    expect(getSession()).toBeNull();
    expect(Object.keys(sessionStorage).filter((k) => k.startsWith('wb_board:'))).toEqual([]);
  });

  it('signing in as someone else starts from a clean view', () => {
    saveSession(who);
    expect(getSession()).toEqual(who);
    expect(sessionStorage.getItem('wb_board:own')).toBeNull();
    expect(sessionStorage.getItem('wb_board:npi-id')).toBeNull();
  });
});
