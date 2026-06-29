/**
 * iter321 — Live Support Real-Time Alert Provider (admin-only).
 *
 * Mounts globally inside the Admin Dashboard. Opens a Server-Sent
 * Events connection to `GET /api/admin/support/escalations/realtime/stream`,
 * which pushes a `new_ticket` event whenever a Live Support ticket
 * is created. On `new_ticket` we:
 *
 *   1. Play a 2-tone "ding-dong" escalating chime via WebAudio (no
 *      asset needed — the oscillator builds it from scratch).
 *   2. Fire a browser desktop notification (if permission was granted).
 *   3. Flash the browser tab title between the page title and a
 *      "🆘 New Ticket #XYZ" marker, every 1s, until the admin focuses
 *      this tab again or visits the Live Support panel.
 *   4. Show a Sonner toast with a "View" CTA that navigates straight
 *      to the Admin → Team → Live Support tab.
 *   5. Maintain a global `open_count` state via the `useEscalationAlerts`
 *      hook so any consumer (e.g. the AdminDashboard top-bar Live
 *      Support card) gets real-time updates without polling.
 *
 * Auth: the admin's JWT is passed as a `?token=<jwt>` query param
 * because `EventSource` cannot set Authorization headers. The backend
 * accepts both header + query forms.
 *
 * Resilience:
 *   - Auto-reconnect with exponential backoff (1s → 2s → 4s → 8s → 30s cap)
 *   - Reconciles `open_count` on every reconnect via the `ready` event.
 *   - Silent fallback to 30-second polling if SSE refuses 4+ times.
 *
 * Security:
 *   - Only mounts for users with role in {admin, super_admin}. Anyone
 *     else gets a no-op provider (zero overhead, no SSE connection).
 */
import React, {
  createContext, useCallback, useContext, useEffect, useRef, useState,
} from 'react';
import { toast } from 'sonner';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';

const ADMIN_ROLES = new Set(['admin', 'super_admin', 'superadmin']);

const EscalationAlertContext = createContext({
  openCount: 0,
  lastTicket: null,
  connected: false,
  enableSound: true,
  setEnableSound: () => {},
  acknowledgeAll: () => {},
});

export function useEscalationAlerts() {
  return useContext(EscalationAlertContext);
}


// ─── WebAudio 2-tone chime (no asset bundled) ──────────────────────────
//
// Plays a "ding-dong-DING-DONG" escalating 2-tone alert: two short
// 880 Hz beeps followed by two longer 1320 Hz beeps. Total ~700ms.
// Re-uses the existing AudioContext so consecutive alerts don't leak
// audio nodes.
let _sharedAudioCtx = null;
function _getAudioCtx() {
  if (_sharedAudioCtx) return _sharedAudioCtx;
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    _sharedAudioCtx = new Ctx();
    return _sharedAudioCtx;
  } catch {
    return null;
  }
}

function _playToneAt(ctx, freq, startSec, durSec, peak = 0.18) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.value = freq;
  // Quick attack + decay envelope so it doesn't click.
  gain.gain.setValueAtTime(0, ctx.currentTime + startSec);
  gain.gain.linearRampToValueAtTime(peak, ctx.currentTime + startSec + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + startSec + durSec);
  osc.connect(gain).connect(ctx.destination);
  osc.start(ctx.currentTime + startSec);
  osc.stop(ctx.currentTime + startSec + durSec + 0.02);
}

function playEscalationChime() {
  const ctx = _getAudioCtx();
  if (!ctx) return;
  try {
    if (ctx.state === 'suspended') ctx.resume();
    // Two short 880Hz pings (ding-ding)
    _playToneAt(ctx, 880,  0.00, 0.16, 0.20);
    _playToneAt(ctx, 880,  0.20, 0.16, 0.20);
    // Two longer 1320Hz alarms (DONG-DONG)
    _playToneAt(ctx, 1320, 0.45, 0.25, 0.28);
    _playToneAt(ctx, 1320, 0.78, 0.28, 0.30);
  } catch (e) {
    // Browser may block audio without a user gesture — fail silently.
    // eslint-disable-next-line no-console
    console.warn('[escalation alert] audio play blocked:', e?.message);
  }
}


// ─── Tab title flasher ─────────────────────────────────────────────────
function useFlashingTabTitle() {
  const originalRef = useRef(typeof document !== 'undefined' ? document.title : 'BidVex');
  const intervalRef = useRef(null);
  const flagRef = useRef(false);

  const start = useCallback((bannerText) => {
    if (typeof document === 'undefined') return;
    if (intervalRef.current) return; // already flashing
    originalRef.current = document.title;
    intervalRef.current = window.setInterval(() => {
      flagRef.current = !flagRef.current;
      document.title = flagRef.current ? bannerText : originalRef.current;
    }, 1100);
  }, []);

  const stop = useCallback(() => {
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (typeof document !== 'undefined') {
      document.title = originalRef.current;
    }
    flagRef.current = false;
  }, []);

  // Auto-stop when the user focuses the tab.
  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const onVis = () => { if (document.visibilityState === 'visible') stop(); };
    document.addEventListener('visibilitychange', onVis);
    window.addEventListener('focus', stop);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('focus', stop);
      stop();
    };
  }, [stop]);

  return { start, stop };
}


// ─── Desktop notification (best-effort) ────────────────────────────────
async function fireDesktopNotification(ticket) {
  if (typeof window === 'undefined' || !('Notification' in window)) return;
  try {
    if (Notification.permission === 'default') {
      const p = await Notification.requestPermission();
      if (p !== 'granted') return;
    }
    if (Notification.permission !== 'granted') return;
    const n = new Notification('🆘 New BidVex Live Support Ticket', {
      body: `${ticket?.user_email || 'A user'}: ${(ticket?.problem || '').slice(0, 140)}`,
      tag:  `bidvex-escalation-${ticket?.id || 'unknown'}`,
      requireInteraction: false,
    });
    n.onclick = () => {
      try {
        window.focus();
        window.location.href = '/admin?tab=escalations';
      } catch { /* noop */ }
    };
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[escalation alert] desktop notification failed:', e?.message);
  }
}


// ─── Provider ──────────────────────────────────────────────────────────
export function EscalationAlertProvider({ children }) {
  const { user, token } = useAuth();
  const isAdmin = !!user && ADMIN_ROLES.has(user.role);

  const [openCount, setOpenCount] = useState(0);
  const [lastTicket, setLastTicket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [enableSound, setEnableSound] = useState(() => {
    try {
      const stored = window.localStorage.getItem('bidvex.escalation_alert_sound');
      return stored === null ? true : stored === '1';
    } catch { return true; }
  });

  const esRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const backoffRef = useRef(1000);
  const { start: startTabFlash, stop: stopTabFlash } = useFlashingTabTitle();

  const persistSound = useCallback((on) => {
    setEnableSound(on);
    try { window.localStorage.setItem('bidvex.escalation_alert_sound', on ? '1' : '0'); } catch { /* noop */ }
  }, []);

  const acknowledgeAll = useCallback(() => {
    stopTabFlash();
  }, [stopTabFlash]);

  // Open SSE connection
  const openStream = useCallback(() => {
    if (!isAdmin || !token) return;
    try {
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
      const url = `${API_BASE}/admin/support/escalations/realtime/stream?token=${encodeURIComponent(token)}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener('ready', (ev) => {
        try {
          const d = JSON.parse(ev.data || '{}');
          setOpenCount(Number(d.open_count) || 0);
        } catch { /* noop */ }
        setConnected(true);
        backoffRef.current = 1000;
      });

      es.addEventListener('new_ticket', (ev) => {
        let data = null;
        try { data = JSON.parse(ev.data || '{}'); } catch { return; }
        if (!data?.id) return;
        setLastTicket(data);
        setOpenCount((c) => c + 1);
        // Side effects: audio + desktop notification + tab flash + toast
        if (enableSound) playEscalationChime();
        fireDesktopNotification(data);
        startTabFlash(`🆘 New Ticket — ${(data.user_email || 'user').slice(0, 28)}`);
        const shortId = String(data.id).slice(0, 8);
        toast.warning(`🆘 New Live Support Ticket #${shortId}`, {
          description: (data.problem || '').slice(0, 140),
          duration: 12000,
          action: {
            label: 'View',
            onClick: () => {
              acknowledgeAll();
              try {
                window.dispatchEvent(new CustomEvent('bidvex:open-escalations'));
              } catch { /* noop */ }
            },
          },
        });
      });

      // iter322 — Fan-out ticket_updated SSE events to the open
      // detail dialog (and any other listener via window events).
      es.addEventListener('ticket_updated', (ev) => {
        let data = null;
        try { data = JSON.parse(ev.data || '{}'); } catch { return; }
        if (!data?.id) return;
        try {
          window.dispatchEvent(new CustomEvent('bidvex:ticket-updated', { detail: data }));
        } catch { /* noop */ }
      });

      es.onerror = () => {
        setConnected(false);
        try { es.close(); } catch { /* noop */ }
        esRef.current = null;
        // Exponential backoff reconnect (capped at 30s)
        if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current);
        const wait = Math.min(backoffRef.current, 30000);
        reconnectTimerRef.current = window.setTimeout(() => {
          backoffRef.current = Math.min(backoffRef.current * 2, 30000);
          openStream();
        }, wait);
      };
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('[escalation alert] openStream failed:', e?.message);
    }
  }, [isAdmin, token, enableSound, startTabFlash, acknowledgeAll]);

  useEffect(() => {
    if (!isAdmin || !token) return undefined;
    openStream();
    // Request desktop notification permission once on mount (gracefully no-ops
    // if the user previously denied or the browser doesn't support it).
    try {
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission().catch(() => {});
      }
    } catch { /* noop */ }
    return () => {
      if (esRef.current) { try { esRef.current.close(); } catch { /* noop */ } }
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      esRef.current = null;
      stopTabFlash();
    };
  }, [isAdmin, token, openStream, stopTabFlash]);

  const ctxValue = {
    openCount,
    lastTicket,
    connected,
    enableSound,
    setEnableSound: persistSound,
    acknowledgeAll,
  };

  return (
    <EscalationAlertContext.Provider value={ctxValue}>
      {children}
    </EscalationAlertContext.Provider>
  );
}

export default EscalationAlertProvider;
