import React, { useState, useEffect } from 'react';
import { Bell, BellOff, BellRing } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import {
  getPushPermission,
  subscribeToPush,
  unsubscribeFromPush,
  isPushSubscribed,
} from '../utils/pushNotifications';

/**
 * Notification toggle button for user settings / first-bid prompt.
 * @param {"settings"|"inline"|"prompt"} variant
 */
const PushNotificationToggle = ({ variant = 'settings' }) => {
  const { token } = useAuth();
  const [subscribed, setSubscribed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [permission, setPermission] = useState('default');

  useEffect(() => {
    setPermission(getPushPermission());
    isPushSubscribed().then(setSubscribed);
  }, []);

  const handleToggle = async () => {
    if (!token) {
      toast.error('Please log in to enable notifications');
      return;
    }
    setLoading(true);
    try {
      if (subscribed) {
        await unsubscribeFromPush(token);
        setSubscribed(false);
        toast.success('Notifications disabled');
      } else {
        const result = await subscribeToPush(token);
        if (result?.ok) {
          setSubscribed(true);
          toast.success('Notifications enabled! You\'ll be alerted for outbids and watchlist items.');
        } else {
          // iter211 — precise messaging per failure code (was: always "check browser permissions")
          const code = result?.code || 'subscribe_failed';
          const detail = result?.detail ? ` (${result.detail})` : '';
          const msg = {
            unsupported: 'Push notifications are not supported in this browser.',
            no_vapid_key: 'Push notifications are not configured on this site. Please contact support.',
            permission_denied: 'Browser permission was denied. Allow notifications in your browser settings and try again.',
            permission_default: 'Browser permission prompt was dismissed. Click "Enable" again to retry.',
            no_service_worker: 'The service worker is not ready yet. Please reload the page and try again.',
            subscribe_failed: 'Could not register with the push service. Please try again in a moment.',
            backend_save_failed: 'Notifications are configured but the server could not save your registration. Please try again.',
            network_error: 'Could not reach the BidVex server. Check your internet connection and try again.',
          }[code] || 'Could not enable notifications. Please try again.';
          toast.error(msg + detail);
          // eslint-disable-next-line no-console
          console.error('[push toggle] subscribe failed:', code, detail);
        }
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[push toggle] unexpected error:', err);
      toast.error('Failed to update notification settings');
    }
    setLoading(false);
    setPermission(getPushPermission());
  };

  if (permission === 'unsupported') return null;

  if (variant === 'prompt') {
    if (subscribed || permission === 'denied') return null;
    return (
      <div
        data-testid="push-notification-prompt"
        className="flex items-center gap-3 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-lg p-3"
      >
        <BellRing className="w-5 h-5 text-amber-600 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-amber-900">Never miss an outbid</p>
          <p className="text-xs text-amber-700">Get instant alerts when someone outbids you</p>
        </div>
        <Button
          data-testid="enable-push-notifications-btn"
          size="sm"
          variant="outline"
          className="border-amber-300 text-amber-800 hover:bg-amber-100 shrink-0"
          onClick={handleToggle}
          disabled={loading}
        >
          {loading ? 'Enabling...' : 'Enable'}
        </Button>
      </div>
    );
  }

  if (variant === 'inline') {
    return (
      <Button
        data-testid="push-notification-toggle-inline"
        size="sm"
        variant={subscribed ? 'default' : 'outline'}
        onClick={handleToggle}
        disabled={loading || permission === 'denied'}
        className="gap-2"
      >
        {subscribed ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
        {loading ? '...' : subscribed ? 'Notifications On' : 'Enable Alerts'}
      </Button>
    );
  }

  // Settings variant (full row)
  return (
    <div
      data-testid="push-notification-settings"
      className="flex items-center justify-between p-4 border rounded-lg"
    >
      <div className="flex items-center gap-3">
        {subscribed ? (
          <Bell className="w-5 h-5 text-green-600" />
        ) : (
          <BellOff className="w-5 h-5 text-slate-400" />
        )}
        <div>
          <p className="font-medium text-sm">Push Notifications</p>
          <p className="text-xs text-muted-foreground">
            {permission === 'denied'
              ? 'Blocked in browser settings'
              : subscribed
              ? 'Outbid alerts & watchlist reminders active'
              : 'Get instant alerts for outbids and ending auctions'}
          </p>
        </div>
      </div>
      <Button
        data-testid="push-notification-toggle-btn"
        size="sm"
        variant={subscribed ? 'destructive' : 'default'}
        onClick={handleToggle}
        disabled={loading || permission === 'denied'}
      >
        {loading ? '...' : subscribed ? 'Disable' : 'Enable'}
      </Button>
    </div>
  );
};

export default PushNotificationToggle;
