/**
 * iter272 — UTM / campaign tracking lifecycle helper.
 *
 * Captures incoming campaign attribution params (`utm_source`,
 * `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, plus a
 * private `bvx_t` token if external campaigns ever sign one) from the
 * URL the very first time a visitor lands. Persists them in
 * `localStorage` with a 30-day TTL so the binding survives:
 *
 *   • Multi-step signup
 *   • Bouncing to a different page before registering
 *   • A page reload mid-form
 *
 * On registration the persisted blob is read once via
 * `consumeCampaignTracking()` and shipped to the backend, which then
 * increments `external_email_campaigns.analytics.registrations`.
 *
 * Designed to be tiny, side-effect-free outside of `localStorage`, and
 * safe to call repeatedly — only the FIRST UTM-bearing visit is
 * persisted. Subsequent visits do NOT overwrite the original
 * attribution (industry-standard first-touch model).
 */

const STORAGE_KEY = 'bvx_campaign_attribution';
const TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

const UTM_KEYS = [
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
];

const EXTRA_KEYS = ['bvx_t', 'bvx_cid'];


function _safeStorage() {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return null;
    const probe = '__bvx_probe__';
    window.localStorage.setItem(probe, '1');
    window.localStorage.removeItem(probe);
    return window.localStorage;
  } catch (_) {
    return null;
  }
}


function _now() { return Date.now(); }


export function captureCampaignTracking(search) {
  const store = _safeStorage();
  if (!store) return null;

  const qs = (search || (typeof window !== 'undefined' ? window.location.search : '')) || '';
  if (!qs || qs.length < 4) return _read(store);

  const params = new URLSearchParams(qs.startsWith('?') ? qs : `?${qs}`);
  const captured = {};
  for (const k of UTM_KEYS.concat(EXTRA_KEYS)) {
    const v = params.get(k);
    if (v && v.length > 0 && v.length <= 200) {
      captured[k] = v;
    }
  }
  if (Object.keys(captured).length === 0) {
    return _read(store);
  }

  // First-touch model: do not overwrite a prior attribution.
  const existing = _read(store);
  if (existing && existing.utm_campaign) {
    return existing;
  }

  const blob = {
    ...captured,
    landing_url: typeof window !== 'undefined' ? window.location.href : null,
    captured_at: _now(),
    expires_at: _now() + TTL_MS,
  };
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(blob));
  } catch (_) { /* quota / private mode */ }
  return blob;
}


function _read(store) {
  try {
    const raw = store.getItem(STORAGE_KEY);
    if (!raw) return null;
    const blob = JSON.parse(raw);
    if (!blob || typeof blob !== 'object') return null;
    if (blob.expires_at && blob.expires_at < _now()) {
      store.removeItem(STORAGE_KEY);
      return null;
    }
    return blob;
  } catch (_) {
    return null;
  }
}


export function readCampaignTracking() {
  const store = _safeStorage();
  if (!store) return null;
  return _read(store);
}


/**
 * Read + clear in a single call — used at signup so the same blob
 * is never double-attributed to multiple users.
 */
export function consumeCampaignTracking() {
  const store = _safeStorage();
  if (!store) return null;
  const blob = _read(store);
  try { store.removeItem(STORAGE_KEY); } catch (_) { /* noop */ }
  return blob;
}


export function buildSignupTrackingPayload() {
  const blob = readCampaignTracking();
  if (!blob) return {};
  return {
    utm_source:   blob.utm_source || null,
    utm_medium:   blob.utm_medium || null,
    utm_campaign: blob.utm_campaign || null,
    utm_term:     blob.utm_term || null,
    utm_content:  blob.utm_content || null,
    bvx_t:        blob.bvx_t || null,
    bvx_cid:      blob.bvx_cid || null,
    landing_url:  blob.landing_url || null,
    captured_at:  blob.captured_at || null,
  };
}
