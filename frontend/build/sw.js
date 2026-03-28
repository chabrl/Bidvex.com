/**
 * BidVex Service Worker
 * Handles push notifications for:
 * - Auction won alerts ("You Won!")
 * - Outbid alerts
 * - New message notifications
 * - Auction ending soon reminders
 */

const CACHE_NAME = 'bidvex-v1';
const NOTIFICATION_ICONS = {
  auction_won: '/android-chrome-192x192.png',
  outbid: '/android-chrome-192x192.png',
  new_message: '/android-chrome-192x192.png',
  auction_ending: '/android-chrome-192x192.png',
  default: '/android-chrome-192x192.png'
};

// Install event
self.addEventListener('install', (event) => {
  console.log('[BidVex SW] Service Worker installing...');
  self.skipWaiting();
});

// Activate event
self.addEventListener('activate', (event) => {
  console.log('[BidVex SW] Service Worker activated');
  event.waitUntil(clients.claim());
});

// Push notification received
self.addEventListener('push', (event) => {
  console.log('[BidVex SW] Push notification received');
  
  let data = {
    title: 'BidVex Notification',
    body: 'You have a new notification',
    type: 'default',
    url: '/'
  };
  
  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch (e) {
      data.body = event.data.text();
    }
  }
  
  const options = {
    body: data.body,
    icon: NOTIFICATION_ICONS[data.type] || NOTIFICATION_ICONS.default,
    badge: '/favicon.png',
    vibrate: [200, 100, 200],
    tag: data.type + '-' + (data.id || Date.now()),
    renotify: true,
    data: {
      url: data.url || '/',
      type: data.type,
      listing_id: data.listing_id,
      conversation_id: data.conversation_id
    },
    actions: getNotificationActions(data.type)
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Get contextual notification actions
function getNotificationActions(type) {
  switch (type) {
    case 'auction_won':
      return [
        { action: 'view', title: '🎉 View Item' },
        { action: 'message', title: '💬 Message Seller' }
      ];
    case 'outbid':
      return [
        { action: 'bid', title: '💰 Place Bid' },
        { action: 'view', title: '👀 View Auction' }
      ];
    case 'new_message':
      return [
        { action: 'reply', title: '💬 Reply' },
        { action: 'dismiss', title: '✕ Dismiss' }
      ];
    case 'auction_ending':
      return [
        { action: 'bid', title: '⚡ Quick Bid' },
        { action: 'view', title: '👀 View' }
      ];
    default:
      return [];
  }
}

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  console.log('[BidVex SW] Notification clicked:', event.action);
  
  event.notification.close();
  
  const data = event.notification.data;
  let targetUrl = '/';
  
  // Determine target URL based on action and notification type
  switch (event.action) {
    case 'view':
    case 'bid':
      if (data.listing_id) {
        targetUrl = `/listing/${data.listing_id}`;
      }
      break;
    case 'message':
    case 'reply':
      if (data.conversation_id) {
        targetUrl = `/messages?conversation=${data.conversation_id}`;
      } else {
        targetUrl = '/messages';
      }
      break;
    case 'dismiss':
      return;
    default:
      targetUrl = data.url || '/';
  }
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Focus existing window if available
        for (const client of clientList) {
          if (client.url.includes(targetUrl) && 'focus' in client) {
            return client.focus();
          }
        }
        // Open new window
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
  );
});

// Handle notification close
self.addEventListener('notificationclose', (event) => {
  console.log('[BidVex SW] Notification closed');
});

// Message handler for communication with main thread
self.addEventListener('message', (event) => {
  console.log('[BidVex SW] Message received:', event.data);
  
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
