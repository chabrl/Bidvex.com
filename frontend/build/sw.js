/**
 * BidVex Service Worker — Push Notifications + Offline Caching
 * Self-hosted VAPID Web Push — no Firebase dependency.
 */
const CACHE_NAME = 'bidvex-v3';
const STATIC_ASSETS = ['/offline.html'];

/* ─── Install ─── */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

/* ─── Activate ─── */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

/* ─── Push Notification ─── */
self.addEventListener('push', (event) => {
  if (!event.data) return;

  let data;
  try {
    data = event.data.json();
  } catch {
    data = { title: 'BidVex', body: event.data.text() };
  }

  const title = data.title || 'BidVex';
  const options = {
    body: data.body || '',
    icon: '/logo192.png',
    badge: '/logo192.png',
    tag: data.type || 'default',
    renotify: true,
    data: {
      url: data.url || '/',
      listing_id: data.listing_id,
      category: data.category,
      type: data.type,
    },
    actions: [],
  };

  // Contextual actions based on notification type
  if (data.type === 'outbid') {
    options.actions = [
      { action: 'counter-bid', title: 'Counter-Bid' },
      { action: 'dismiss', title: 'Dismiss' },
    ];
    options.requireInteraction = true;
  } else if (data.type === 'watchlist_expiry') {
    options.actions = [
      { action: 'view', title: 'View Auction' },
      { action: 'dismiss', title: 'Dismiss' },
    ];
    options.requireInteraction = true;
  }

  event.waitUntil(self.registration.showNotification(title, options));
});

/* ─── Notification Click ─── */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const data = event.notification.data || {};
  let targetUrl = data.url || '/';

  // Smart routing: use the pre-computed URL from the push payload
  // The backend already determines /vehicle-auctions/ vs /listing/ based on category
  if (event.action === 'counter-bid' || event.action === 'view') {
    targetUrl = data.url || '/';
  } else if (event.action === 'dismiss') {
    return;
  }

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      // If there's already an open BidVex tab, navigate it
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && 'navigate' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      // Otherwise open a new tab
      return self.clients.openWindow(targetUrl);
    })
  );
});

/* ─── Message Handler (skip waiting on demand) ─── */
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

/* ─── Fetch: Network-first, offline fallback ─── */
self.addEventListener('fetch', (event) => {
  // Skip non-GET and API requests
  if (event.request.method !== 'GET' || event.request.url.includes('/api/')) return;

  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match(event.request).then((cached) => cached || caches.match('/offline.html'))
    )
  );
});
