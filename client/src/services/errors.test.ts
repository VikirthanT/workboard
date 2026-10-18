/* The server sends `{detail: {code, message}}`; the mock sends `{detail: "text"}`; FastAPI's own 422 sends a list. */
import { describe, expect, it } from 'vitest';
import { errorCode, errorMessage } from './axiosInstance';

const failed = (detail: unknown) => ({ response: { data: { detail } }, message: 'Request failed with status code 4xx' });

describe('errorMessage', () => {
  it('reads the server shape, the mock shape and the 422 list', () => {
    expect(errorMessage(failed({ code: 'reason_required', message: 'Give a reason.' }))).toBe('Give a reason.');
    expect(errorMessage(failed('Only @atimotors.com accounts are allowed.'))).toBe('Only @atimotors.com accounts are allowed.');
    expect(errorMessage(failed([{ msg: 'String should have at most 140 characters' }]))).toBe('String should have at most 140 characters');
  });

  it('falls back to the network error, then to the given text', () => {
    expect(errorMessage({ message: 'Network Error' })).toBe('Network Error');
    expect(errorMessage({}, 'Sign in failed.')).toBe('Sign in failed.');
  });
});

describe('errorCode', () => {
  it('is the server code, or the mock string, and nothing for a 422 list', () => {
    expect(errorCode(failed({ code: 'not_onboarded', message: 'x' }))).toBe('not_onboarded');
    expect(errorCode(failed('domain_not_allowed'))).toBe('domain_not_allowed');
    expect(errorCode(failed([{ msg: 'x' }]))).toBeUndefined();
    expect(errorCode({})).toBeUndefined();
  });
});
