/**
 * BidVex Push Notification Utilities
 * Self-hosted VAPID Web Push — registers SW and manages subscriptions.
 */

const VAPID_PUBLIC_KEY = process.env.REACT_APP_VAPID_PUBLIC_KEY || '';

/**
 * Convert VAPID public key (base64url) to Uint8Array for the PushManager.
 */
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; ++i) output[i] = raw.charCodeAt(i);
  return output;
}

/**
 * Register the service worker and return the registration.
 */
export async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return null;
  try {
    const reg = await navigator.serviceWorker.register('/sw.js');
    return reg;
  } catch (err) {
    console.warn('[Push] SW registration failed:', err);
    return null;
  }
}

/**
 * Check if push is supported and permission status.
 */
export function getPushPermission() {
  if (!('Notification' in window)) return 'unsupported';
  return Notification.permission; // 'default', 'granted', 'denied'
}

/**
 * Request push permission and subscribe to VAPID push.
 * Sends subscription to backend for storage.
 * @param {string} token - JWT auth token
 * @returns {boolean} success
 */
export async function subscribeToPush(token) {
  if (!('PushManager' in window) || !VAPID_PUBLIC_KEY) return false;

  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return false;

    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();

    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });
    }

    const subJson = sub.toJSON();
    const apiBase = process.env.REACT_APP_BACKEND_URL || '';

    await fetch(`${apiBase}/api/push/subscribe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        endpoint: subJson.endpoint,
        keys: subJson.keys,
      }),
    });

    return true;
  } catch (err) {
    console.warn('[Push] Subscribe failed:', err);
    return false;
  }
}

/**
 * Unsubscribe from push notifications.
 * @param {string} token - JWT auth token
 */
export async function unsubscribeFromPush(token) {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return true;

    const subJson = sub.toJSON();
    const apiBase = process.env.REACT_APP_BACKEND_URL || '';

    await fetch(`${apiBase}/api/push/unsubscribe`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        endpoint: subJson.endpoint,
        keys: subJson.keys,
      }),
    });

    await sub.unsubscribe();
    return true;
  } catch (err) {
    console.warn('[Push] Unsubscribe failed:', err);
    return false;
  }
}

/**
 * Check if the user currently has an active push subscription.
 */
export async function isPushSubscribed() {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return !!sub;
  } catch {
    return false;
  }
}

/**
 * Show a local notification (for testing / in-app fallback).
 */
export async function showLocalNotification(title, body, data = {}) {
  if (Notification.permission !== 'granted') return;
  const reg = await navigator.serviceWorker.ready;
  reg.showNotification(title, {
    body,
    icon: '/logo192.png',
    badge: '/logo192.png',
    data,
  });
}

export default {
  registerServiceWorker,
  getPushPermission,
  subscribeToPush,
  unsubscribeFromPush,
  isPushSubscribed,
  showLocalNotification,
};
