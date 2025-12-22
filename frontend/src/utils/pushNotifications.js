/**
 * BidVex Push Notifications Utility
 * Handles Service Worker registration and push subscription management
 */

const PUBLIC_VAPID_KEY = process.env.REACT_APP_VAPID_PUBLIC_KEY || null;

/**
 * Check if push notifications are supported
 */
export const isPushSupported = () => {
  return 'serviceWorker' in navigator && 'PushManager' in window;
};

/**
 * Register the service worker
 */
export const registerServiceWorker = async () => {
  if (!('serviceWorker' in navigator)) {
    console.warn('[BidVex] Service workers not supported');
    return null;
  }
  
  try {
    const registration = await navigator.serviceWorker.register('/sw.js', {
      scope: '/'
    });
    
    console.log('[BidVex] Service Worker registered:', registration.scope);
    
    // Check for updates
    registration.addEventListener('updatefound', () => {
      const newWorker = registration.installing;
      console.log('[BidVex] Service Worker update found');
      
      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          console.log('[BidVex] New Service Worker ready');
        }
      });
    });
    
    return registration;
  } catch (error) {
    console.error('[BidVex] Service Worker registration failed:', error);
    return null;
  }
};

/**
 * Request notification permission
 */
export const requestNotificationPermission = async () => {
  if (!('Notification' in window)) {
    console.warn('[BidVex] Notifications not supported');
    return 'unsupported';
  }
  
  if (Notification.permission === 'granted') {
    return 'granted';
  }
  
  if (Notification.permission === 'denied') {
    return 'denied';
  }
  
  try {
    const permission = await Notification.requestPermission();
    return permission;
  } catch (error) {
    console.error('[BidVex] Permission request failed:', error);
    return 'error';
  }
};

/**
 * Subscribe to push notifications
 */
export const subscribeToPush = async (registration) => {
  if (!registration) {
    console.warn('[BidVex] No service worker registration');
    return null;
  }
  
  try {
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      ...(PUBLIC_VAPID_KEY && {
        applicationServerKey: urlBase64ToUint8Array(PUBLIC_VAPID_KEY)
      })
    });
    
    console.log('[BidVex] Push subscription created:', subscription.endpoint);
    return subscription;
  } catch (error) {
    console.error('[BidVex] Push subscription failed:', error);
    return null;
  }
};

/**
 * Get current push subscription
 */
export const getSubscription = async () => {
  if (!('serviceWorker' in navigator)) return null;
  
  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    return subscription;
  } catch (error) {
    console.error('[BidVex] Failed to get subscription:', error);
    return null;
  }
};

/**
 * Unsubscribe from push notifications
 */
export const unsubscribeFromPush = async () => {
  try {
    const subscription = await getSubscription();
    if (subscription) {
      await subscription.unsubscribe();
      console.log('[BidVex] Unsubscribed from push');
      return true;
    }
    return false;
  } catch (error) {
    console.error('[BidVex] Unsubscribe failed:', error);
    return false;
  }
};

/**
 * Show local notification (fallback when push not available)
 */
export const showLocalNotification = async (title, options = {}) => {
  if (!('Notification' in window)) return false;
  
  if (Notification.permission !== 'granted') {
    const permission = await requestNotificationPermission();
    if (permission !== 'granted') return false;
  }
  
  try {
    const registration = await navigator.serviceWorker.ready;
    await registration.showNotification(title, {
      icon: '/android-chrome-192x192.png',
      badge: '/favicon.png',
      vibrate: [200, 100, 200],
      ...options
    });
    return true;
  } catch (error) {
    console.error('[BidVex] Show notification failed:', error);
    return false;
  }
};

/**
 * Convert VAPID key to Uint8Array
 */
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  
  return outputArray;
}

/**
 * Initialize push notifications for the app
 */
export const initializePushNotifications = async () => {
  if (!isPushSupported()) {
    console.log('[BidVex] Push notifications not supported');
    return { supported: false };
  }
  
  const registration = await registerServiceWorker();
  if (!registration) {
    return { supported: true, registered: false };
  }
  
  const permission = await requestNotificationPermission();
  
  if (permission === 'granted') {
    const subscription = await subscribeToPush(registration);
    return {
      supported: true,
      registered: true,
      permission: 'granted',
      subscription
    };
  }
  
  return {
    supported: true,
    registered: true,
    permission
  };
};

export default {
  isPushSupported,
  registerServiceWorker,
  requestNotificationPermission,
  subscribeToPush,
  getSubscription,
  unsubscribeFromPush,
  showLocalNotification,
  initializePushNotifications
};
