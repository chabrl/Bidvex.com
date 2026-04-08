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
        const success = await subscribeToPush(token);
        if (success) {
          setSubscribed(true);
          toast.success('Notifications enabled! You\'ll be alerted for outbids and watchlist items.');
        } else {
          toast.error('Could not enable notifications. Check browser permissions.');
        }
      }
    } catch {
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
