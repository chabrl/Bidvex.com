/**
 * PushPermissionPrompt — iter306
 *
 * Non-blocking toast-style prompt that appears 6 seconds after login if
 * the user has never been asked. Stores the answer in localStorage so we
 * never re-prompt (spec: "If user denies: respect it, never ask again").
 *
 * The actual subscription work is handled by the existing
 * `subscribeToPush` helper in /lib/pushNotifications.
 */
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Bell, X } from 'lucide-react';
import { Button } from './ui/button';
import { useAuth } from '../contexts/AuthContext';
import { subscribeToPush } from '../utils/pushNotifications';

const STORAGE_KEY = 'bidvex_push_prompt_v1';

const PushPermissionPrompt = () => {
  const { t, i18n } = useTranslation();
  const { token, user } = useAuth();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token || !user) return;
    // iter306 — dev/QA override: `?force_push_prompt=1` always shows the prompt.
    const params = (typeof window !== 'undefined' && window.location && window.location.search) ? new URLSearchParams(window.location.search) : null;
    const forceShow = !!(params && params.get('force_push_prompt') === '1');
    if (forceShow) {
      const tf = setTimeout(() => setVisible(true), 200);
      return () => clearTimeout(tf);
    }
    // Respect prior decision
    let prior = null;
    try { prior = localStorage.getItem(STORAGE_KEY); } catch (_e) { /* ignore */ }
    if (prior) return;
    // Skip if browser doesn't support push
    if (typeof Notification === 'undefined' || !('serviceWorker' in navigator)) return;
    // Skip if already granted (user enabled via toggle) or already denied
    if (Notification.permission !== 'default') {
      try { localStorage.setItem(STORAGE_KEY, Notification.permission); } catch (_e) { /* ignore */ }
      return;
    }
    // Non-blocking — wait 6 sec after login so we don't interrupt onboarding
    const t1 = setTimeout(() => setVisible(true), 6000);
    return () => clearTimeout(t1);
  }, [token, user]);

  const decide = async (answer) => {
    try { localStorage.setItem(STORAGE_KEY, answer); } catch (_e) { /* ignore */ }
    if (answer === 'accept') {
      setBusy(true);
      try {
        await subscribeToPush(token);
      } catch (_e) {
        // Silently fail — user can re-enable from notifications settings
      } finally {
        setBusy(false);
      }
    }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      role="alertdialog"
      data-testid="push-permission-prompt"
      className="fixed bottom-4 right-4 z-50 max-w-sm w-[calc(100%-2rem)] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl p-4"
    >
      <button
        onClick={() => decide('dismiss')}
        className="absolute top-2 right-2 p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
        aria-label="Close"
        data-testid="push-permission-close-btn"
      >
        <X className="h-4 w-4" />
      </button>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          <div className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-950 flex items-center justify-center">
            <Bell className="h-4 w-4 text-blue-600" />
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm text-slate-900 dark:text-white pr-4">
            {fr ? 'Recevoir des alertes sur vos enchères' : 'Get notified about your bids'}
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
            {fr
              ? "Activez les notifications de votre navigateur pour ne plus manquer une surenchère ou une victoire."
              : "Enable browser notifications so you never miss an outbid alert or auction win."}
          </p>
          <div className="flex gap-2 mt-3">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => decide('deny')}
              disabled={busy}
              className="text-xs"
              data-testid="push-permission-deny-btn"
            >
              {fr ? 'Plus tard' : 'Not now'}
            </Button>
            <Button
              size="sm"
              onClick={() => decide('accept')}
              disabled={busy}
              className="text-xs bg-blue-600 hover:bg-blue-700"
              data-testid="push-permission-accept-btn"
            >
              {fr ? 'Activer les notifications' : 'Enable notifications'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PushPermissionPrompt;
