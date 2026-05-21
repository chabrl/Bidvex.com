/**
 * BidVex — Centralized auth token + axios header helper (iter214).
 *
 * The static analyzer flagged 13 high-severity + 106 medium-severity raw
 * `localStorage.getItem('token')` reads across the codebase. Migrating every
 * one of them to httpOnly cookies is a multi-session backend refactor. As a
 * stop-gap, ALL token access now flows through this single helper so:
 *
 *   1. There is exactly ONE chokepoint where the storage backend is read
 *      (making the eventual httpOnly cookie migration a 1-file change).
 *   2. The helper returns `null` for missing/expired tokens (no exceptions).
 *   3. Components never touch localStorage directly for credentials.
 *
 * Public API:
 *   getAuthToken()                  → string | null
 *   authHeaders()                   → { Authorization: 'Bearer …' } | {}
 *   clearAuthToken()                → clears local copy (used on logout)
 *   setAuthToken(token)             → persists token after login/refresh
 */

const _STORAGE_KEY = 'token';

export function getAuthToken() {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(_STORAGE_KEY) || null;
  } catch (readErr) {
    // Safari private mode / SSR / quota-exceeded — fail silently.
    console.debug('[authToken] read failed:', readErr);
    return null;
  }
}

export function authHeaders() {
  const t = getAuthToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export function setAuthToken(token) {
  if (typeof window === 'undefined') return;
  try {
    if (token) {
      window.localStorage.setItem(_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(_STORAGE_KEY);
    }
  } catch (writeErr) {
    console.debug('[authToken] write failed:', writeErr);
  }
}

export function clearAuthToken() {
  setAuthToken(null);
}
