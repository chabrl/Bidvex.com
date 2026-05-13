/**
 * BidVex — Web Push Subscription helpers.
 *
 * iter211 rewrite — distinguishes WHY a subscription failed so the UI can show
 * an accurate error instead of always blaming the browser permission. The
 * previous version swallowed every error path and returned `false`, which made
 * the user-facing toast misleading.
 *
 * Error codes returned (rejection reasons):
 *   • "unsupported"          — Service Worker / PushManager not supported
 *   • "no_vapid_key"         — REACT_APP_VAPID_PUBLIC_KEY missing at build time
 *   • "permission_denied"    — User clicked "Block" in the browser prompt
 *   • "permission_default"   — User dismissed the prompt without choosing
 *   • "subscribe_failed"     — pushManager.subscribe() rejected (push service)
 *   • "backend_save_failed"  — POST /api/push/subscribe returned non-2xx
 *   • "network_error"        — fetch() threw (offline / CORS / DNS)
 *   • "no_service_worker"    — navigator.serviceWorker.ready never resolved
 */

const VAPID_PUBLIC_KEY = process.env.REACT_APP_VAPID_PUBLIC_KEY;

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

export function isPushSupported() {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

export async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) {
    console.warn('[push] Service Worker API not supported');
    return null;
  }
  try {
    const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    // eslint-disable-next-line no-console
    console.log('[push] Service Worker registered:', reg.scope);
    return reg;
  } catch (err) {
    console.error('[push] Service Worker registration failed:', err);
    return null;
  }
}

/**
 * Subscribe the current browser to web push.
 *
 * @returns {Promise<{ok: true, subscription: PushSubscription} | {ok: false, code: string, detail?: string}>}
 */
export async function subscribeToPush() {
  if (!isPushSupported()) {
    return { ok: false, code: 'unsupported' };
  }
  if (!VAPID_PUBLIC_KEY) {
    console.error('[push] REACT_APP_VAPID_PUBLIC_KEY is not set at build time');
    return { ok: false, code: 'no_vapid_key' };
  }

  // Wait up to 6 s for the SW registered at app boot. If it never resolves,
  // surface a precise error rather than hanging forever.
  let registration;
  try {
    registration = await Promise.race([
      navigator.serviceWorker.ready,
      new Promise((_r, rej) => setTimeout(() => rej(new Error('sw_ready_timeout')), 6000)),
    ]);
  } catch (err) {
    console.error('[push] Service worker not ready:', err);
    return { ok: false, code: 'no_service_worker', detail: String(err?.message || err) };
  }

  // Request notification permission (idempotent if already granted)
  let permission = Notification.permission;
  if (permission === 'default') {
    permission = await Notification.requestPermission();
  }
  if (permission === 'denied') {
    return { ok: false, code: 'permission_denied' };
  }
  if (permission !== 'granted') {
    return { ok: false, code: 'permission_default' };
  }

  // Create or reuse a PushSubscription
  let sub;
  try {
    sub = await registration.pushManager.getSubscription();
    if (!sub) {
      sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });
    }
  } catch (err) {
    console.error('[push] pushManager.subscribe failed:', err);
    return { ok: false, code: 'subscribe_failed', detail: String(err?.message || err) };
  }

  // Persist on the backend (with credentials). Distinguish:
  //   • network failure (fetch throws) → network_error
  //   • backend non-2xx                → backend_save_failed (with detail)
  const apiBase = process.env.REACT_APP_BACKEND_URL || '';
  const url = `${apiBase}/api/push/subscribe`;
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('token') : null;
  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        subscription: sub.toJSON ? sub.toJSON() : sub,
        user_agent: navigator.userAgent,
      }),
    });
  } catch (err) {
    console.error('[push] backend POST threw:', err);
    return { ok: false, code: 'network_error', detail: String(err?.message || err) };
  }

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    console.error('[push] backend returned', response.status, text);
    // If save failed, undo the local push subscription so a retry doesn't
    // silently use a stale subscription the server doesn't know about.
    try { await sub.unsubscribe(); } catch (_) { /* best-effort */ }
    return {
      ok: false,
      code: 'backend_save_failed',
      detail: `HTTP ${response.status}${text ? ` — ${text.slice(0, 120)}` : ''}`,
    };
  }

  return { ok: true, subscription: sub };
}

export async function unsubscribeFromPush() {
  if (!isPushSupported()) return false;
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return true;
    const endpoint = sub.endpoint;
    await sub.unsubscribe();
    const apiBase = process.env.REACT_APP_BACKEND_URL || '';
    const token = typeof window !== 'undefined' ? window.localStorage.getItem('token') : null;
    await fetch(`${apiBase}/api/push/unsubscribe`, {
      method: 'DELETE',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ endpoint }),
    }).catch(() => {});
    return true;
  } catch (err) {
    console.error('[push] unsubscribe failed:', err);
    return false;
  }
}

export async function isPushSubscribed() {
  if (!isPushSupported()) return false;
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return !!sub;
  } catch {
    return false;
  }
}

export function showLocalNotification(title, options = {}) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  try { new Notification(title, options); } catch (_) { /* noop */ }
}

export default {
  isPushSupported,
  registerServiceWorker,
  subscribeToPush,
  unsubscribeFromPush,
  isPushSubscribed,
  showLocalNotification,
};
