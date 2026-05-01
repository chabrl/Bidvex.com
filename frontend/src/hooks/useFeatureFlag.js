/**
 * useFeatureFlag — iter176
 * =========================
 * Tiny hook that calls GET /api/feature-flags/{key} once per session
 * (with an in-memory cache) and returns { enabled, loading }.
 *
 * The backend sets Cache-Control: max-age=60, and we additionally
 * memoize inside the browser session so the real page vs Coming-Soon
 * decision doesn't flicker on route changes.
 */
import { useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE from '../config';

const cache = new Map(); // key -> { enabled, ts }
const TTL_MS = 60_000;

export default function useFeatureFlag(key) {
  const cached = cache.get(key);
  const fresh = cached && (Date.now() - cached.ts) < TTL_MS;

  const [state, setState] = useState(
    fresh ? { enabled: cached.enabled, loading: false } : { enabled: null, loading: true }
  );

  useEffect(() => {
    if (fresh) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/feature-flags/${key}`);
        const enabled = !!r.data?.enabled;
        cache.set(key, { enabled, ts: Date.now() });
        if (!cancelled) setState({ enabled, loading: false });
      } catch {
        // Fail-closed: treat unreachable flag as disabled (Coming Soon)
        cache.set(key, { enabled: false, ts: Date.now() });
        if (!cancelled) setState({ enabled: false, loading: false });
      }
    })();
    return () => { cancelled = true; };
  }, [key, fresh]);

  return state;
}

/** Imperative cache-buster for admins who just flipped a flag. */
export function invalidateFeatureFlag(key) {
  cache.delete(key);
}
