import API_BASE from '../config';
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { X, MessageCircle, Send, ShieldCheck, CreditCard, Package, HelpCircle, Mail, GripVertical, History, Trash2, ChevronLeft, Square, LifeBuoy, Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

// Mobile bottom-nav height + safe gap. MobileBottomNav.js renders 64px nav
// content + iPhone safe-area-inset-bottom (≈34px on iPhones with home indicator,
// 0px on Android & iPads). We keep a 16px breathing-room gap above the nav.
const MOBILE_NAV_HEIGHT = 64;       // matches --bidvex-mobile-nav-height
const FAB_GAP = 16;                 // breathing room above the nav
const FAB_RIGHT_OFFSET = 16;
const FAB_SIZE = 56;                // 14 in tailwind ≈ 56px (3.5rem)
const STORAGE_KEY = 'bidvex.fabPosition.v1';

// Bottom inset (in px) including iPhone home-indicator safe area.
// Read at runtime by querying a hidden element with `padding-bottom: env(...)`.
const getSafeAreaBottom = () => {
  if (typeof window === 'undefined' || typeof document === 'undefined') return 0;
  const probe = document.createElement('div');
  probe.style.cssText = 'position:fixed;bottom:0;height:0;padding-bottom:env(safe-area-inset-bottom,0px);visibility:hidden;pointer-events:none;';
  document.body.appendChild(probe);
  const v = parseFloat(getComputedStyle(probe).paddingBottom) || 0;
  document.body.removeChild(probe);
  return v;
};

// Total floor offset from bottom of viewport that the FAB must respect:
// nav-height + safe-area-inset-bottom + breathing gap.
const getFabBottomFloor = () => MOBILE_NAV_HEIGHT + getSafeAreaBottom() + FAB_GAP;

const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

const AIAssistant = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Welcome to BidVex! I am the BidVex AI Core, here to help with bidding, account questions, and platform guidance. How may I assist you today?',
      rich_content: null,
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [serviceDegraded, setServiceDegraded] = useState(false);
  // iter239 Mission 4 — Persistent chat history panel state.
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historySessions, setHistorySessions] = useState([]);
  const [sessionId, setSessionId] = useState(() => {
    try { return localStorage.getItem('bidvex.chat.session_id') || ''; } catch { return ''; }
  });
  const persistSessionId = useCallback((sid) => {
    if (!sid) return;
    try { localStorage.setItem('bidvex.chat.session_id', sid); } catch { /* ignore */ }
    setSessionId(sid);
  }, []);
  const messagesEndRef = useRef(null);
  // iter279 — Stop-button support. Holds the AbortController of the
  // currently in-flight stream so the user can interrupt mid-stream
  // without dangling fetches. Cleared on stream completion AND on
  // component unmount (cleanup useEffect at bottom of file).
  const activeStreamCtrlRef = useRef(null);
  const { token } = useAuth();
  const navigate = useNavigate();
  const backendUrl = API_BASE;

  // iter321 — Manual "Talk to a human" fallback state (must be declared
  // AFTER `token`/`backendUrl` to avoid temporal-dead-zone errors in the
  // useCallback closure dependency array).
  const [manualEscalationOpen, setManualEscalationOpen] = useState(false);
  const [manualProblem, setManualProblem] = useState('');
  const [manualDetails, setManualDetails] = useState('');
  const [manualSubmitting, setManualSubmitting] = useState(false);

  const submitManualEscalation = useCallback(async () => {
    const problem = manualProblem.trim();
    const details = manualDetails.trim();
    if (!problem || !token || manualSubmitting) return;
    setManualSubmitting(true);
    const _ESCALATION_RE = /\[\[BIDVEX_ESCALATION\]\]([\s\S]*?)\[\[\/BIDVEX_ESCALATION\]\]/;
    const _strip = (txt) => (txt || '').replace(_ESCALATION_RE, '').trim();
    const recent = (messages || []).slice(-12).map((mm) => ({
      role:    mm.role,
      content: _strip(mm.content),
      ts:      mm.ts || new Date().toISOString(),
    })).filter((mm) => mm.content);
    const isFr = typeof window !== 'undefined' && (window.localStorage.getItem('i18nextLng') || '').startsWith('fr');
    try {
      const r = await fetch(`${backendUrl}/support/escalate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          problem:    problem.slice(0, 1500),
          details:    details.slice(0, 2500),
          language:   isFr ? 'fr' : 'en',
          transcript: recent,
          session_id: sessionId || null,
          page_url:   typeof window !== 'undefined' ? window.location.pathname : null,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const json = await r.json();
      const shortId = String(json.ticket_id || '').slice(0, 8);
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: `[${isFr ? 'Demande humaine' : 'Human request'}] ${problem}`, rich_content: null },
        {
          role: 'assistant',
          content: isFr
            ? `✅ Demande créée : #${shortId} · Un agent vous contactera sous peu.`
            : `✅ Ticket created: #${shortId} · An agent will reach out shortly.`,
          rich_content: null,
          escalation_ticket_id: json.ticket_id,
        },
      ]);
      setManualEscalationOpen(false);
      setManualProblem('');
      setManualDetails('');
      toast.success(isFr ? 'Ticket créé' : 'Ticket created');
    } catch (e) {
      toast.error(isFr ? 'Échec de la création — réessayez ou écrivez à support@bidvex.com' : 'Could not create ticket — retry or email support@bidvex.com');
    } finally {
      setManualSubmitting(false);
    }
  }, [manualProblem, manualDetails, manualSubmitting, token, messages, sessionId, backendUrl]);

  // iter322 — User-side SSE for admin replies on Live Support tickets.
  // When an admin posts a reply via the AdminEscalationsConsole, this
  // EventSource receives an `admin_reply` event and injects a `🛡 Support`
  // bubble into the chat panel (+ a soft chime + optional unread badge bump).
  useEffect(() => {
    if (!token) return undefined;
    let es = null;
    let closed = false;
    let backoff = 1000;
    let reconnectTimer = null;

    const playSoftChime = () => {
      try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        const ctx = new Ctx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = 660;
        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.18, ctx.currentTime + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
        osc.connect(gain).connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.55);
      } catch { /* silently fail — browsers may block audio without user gesture */ }
    };

    const open = () => {
      try {
        es = new EventSource(`${backendUrl}/support/escalations/user/stream?token=${encodeURIComponent(token)}`);
        es.addEventListener('ready', () => { backoff = 1000; });
        es.addEventListener('admin_reply', (ev) => {
          let d = null;
          try { d = JSON.parse(ev.data || '{}'); } catch { return; }
          if (!d?.message) return;
          const shortId = String(d.ticket_id || '').slice(0, 8);
          // Append a styled assistant bubble (rendered identically to AI
          // replies but with the 🛡 Support tag so the user immediately
          // sees it's a human reply).
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: `🛡 **BidVex Support** (Ticket #${shortId})\n\n${d.message}`,
              rich_content: null,
              from_admin: true,
              ticket_id: d.ticket_id,
            },
          ]);
          playSoftChime();
          try {
            // If the chat is closed, bump the unread badge so the user sees
            // they have an unread human reply waiting.
            if (typeof window !== 'undefined') {
              const evt = new CustomEvent('bidvex:admin-reply', { detail: d });
              window.dispatchEvent(evt);
            }
          } catch { /* noop */ }
          toast.success('🛡 Support replied', {
            description: String(d.message || '').slice(0, 140),
            duration: 10000,
          });
        });
        es.onerror = () => {
          if (closed) return;
          try { es?.close(); } catch { /* noop */ }
          es = null;
          if (reconnectTimer) window.clearTimeout(reconnectTimer);
          const wait = Math.min(backoff, 30000);
          reconnectTimer = window.setTimeout(() => {
            backoff = Math.min(backoff * 2, 30000);
            open();
          }, wait);
        };
      } catch { /* noop */ }
    };

    open();
    return () => {
      closed = true;
      try { es?.close(); } catch { /* noop */ }
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
    };
  }, [token, backendUrl]);

  // ── Draggable FAB state ──
  // Position is stored as {x, y} in viewport pixels (from top-left).
  // Default sits the FAB above the mobile bottom-nav at the right edge.
  const computeDefaultPos = () => ({
    x: typeof window !== 'undefined' ? window.innerWidth - FAB_SIZE - FAB_RIGHT_OFFSET : 16,
    y: typeof window !== 'undefined' ? window.innerHeight - FAB_SIZE - getFabBottomFloor() : 88,
  });

  const [fabPos, setFabPos] = useState(() => {
    if (typeof window === 'undefined') return { x: 16, y: 88 };
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (saved && typeof saved.x === 'number' && typeof saved.y === 'number') {
        return {
          x: clamp(saved.x, 8, window.innerWidth - FAB_SIZE - 8),
          y: clamp(saved.y, 8, window.innerHeight - FAB_SIZE - getFabBottomFloor()),
        };
      }
    } catch { /* ignore */ }
    return computeDefaultPos();
  });

  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0, moved: false });

  // Re-clamp on viewport resize / rotation so FAB never falls off-screen.
  useEffect(() => {
    const onResize = () => {
      setFabPos((p) => ({
        x: clamp(p.x, 8, window.innerWidth - FAB_SIZE - 8),
        y: clamp(p.y, 8, window.innerHeight - FAB_SIZE - getFabBottomFloor()),
      }));
    };
    window.addEventListener('resize', onResize);
    window.addEventListener('orientationchange', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('orientationchange', onResize);
    };
  }, []);

  const persistPos = useCallback((p) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(p)); } catch { /* ignore */ }
  }, []);

  // Drag handlers — work for both touch and mouse.
  const onPointerDown = (e) => {
    const point = e.touches ? e.touches[0] : e;
    dragRef.current = {
      dragging: true,
      startX: point.clientX,
      startY: point.clientY,
      origX: fabPos.x,
      origY: fabPos.y,
      moved: false,
    };
  };
  const onPointerMove = (e) => {
    if (!dragRef.current.dragging) return;
    const point = e.touches ? e.touches[0] : e;
    const dx = point.clientX - dragRef.current.startX;
    const dy = point.clientY - dragRef.current.startY;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
      dragRef.current.moved = true;
      e.preventDefault?.();
    }
    if (!dragRef.current.moved) return;
    const nx = clamp(dragRef.current.origX + dx, 8, window.innerWidth - FAB_SIZE - 8);
    const ny = clamp(dragRef.current.origY + dy, 8, window.innerHeight - FAB_SIZE - getFabBottomFloor());
    setFabPos({ x: nx, y: ny });
  };
  const onPointerUp = () => {
    if (!dragRef.current.dragging) return;
    if (dragRef.current.moved) persistPos(fabPos);
    dragRef.current.dragging = false;
  };

  // Click vs drag: only open chat if pointer never moved during the press.
  const handleFabClick = () => {
    if (dragRef.current.moved) return;     // dragged → ignore click
    setIsOpen(true);
  };

  // Reset position to default (long-press or right-click handler optional, exposed in console)
  useEffect(() => {
    window.__bidvexResetFabPos = () => {
      const def = computeDefaultPos();
      setFabPos(def);
      persistPos(def);
    };
    return () => { try { delete window.__bidvexResetFabPos; } catch { /* ignore */ } };
  }, [persistPos]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  // iter235 — Self-heal degraded banner using the lightweight diagnostics
  // endpoint of the new streaming chat path (no LLM call, no cost).
  useEffect(() => {
    if (!serviceDegraded || !isOpen) return undefined;
    let cancelled = false;
    const probe = async () => {
      try {
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 6000);
        const res = await fetch(`${backendUrl}/chat/diagnostics`, {
          method: 'GET',
          signal: ctrl.signal,
        });
        clearTimeout(tid);
        if (!cancelled && res.ok) {
          const data = await res.json().catch(() => null);
          if (data && data.gemini_api_key_present) setServiceDegraded(false);
        }
      } catch {
        // still degraded; loop again
      }
    };
    const id = setInterval(probe, 20000);
    probe(); // immediate first check
    return () => { cancelled = true; clearInterval(id); };
  }, [serviceDegraded, isOpen, backendUrl]);

  const [unreadBadge, setUnreadBadge] = useState(0);
  const originalTitleRef = useRef(typeof document !== 'undefined' ? document.title : 'BidVex');
  const acknowledgmentIdRef = useRef(0);

  // iter236 Mission 3 — Resolve & persist current listing UUID for the chat
  // session. Priority: explicit prop → URL pathname patterns. Re-resolved
  // when the route changes (mount + pathname change). Persists in local
  // state for the duration of the chat so each message ships the same ID.
  const resolveListingIdFromUrl = () => {
    if (typeof window === 'undefined') return null;
    const path = window.location.pathname || '';
    // Patterns supported by router: /listing/:id, /lots/:id, /vehicle-auctions/:id,
    // /vehicles/:id, /storage-auctions/:id, /multi-item-listing/:id, /auction/:id, /lot/:id, /item/:id
    const m = path.match(
      /\/(?:listing|lots|vehicle-auctions|vehicles|storage-auctions|multi-item-listing|auction|lot|item)\/([a-zA-Z0-9_-]{4,})/
    );
    return m ? m[1] : null;
  };
  const [listingIdForChat, setListingIdForChat] = useState(() => resolveListingIdFromUrl());
  useEffect(() => {
    const onLoc = () => setListingIdForChat(resolveListingIdFromUrl());
    window.addEventListener('popstate', onLoc);
    window.addEventListener('hashchange', onLoc);
    // Re-resolve once per chat open (React Router pushState).
    if (isOpen) onLoc();
    return () => {
      window.removeEventListener('popstate', onLoc);
      window.removeEventListener('hashchange', onLoc);
    };
  }, [isOpen]);

  // iter236 Mission 3 — On open, if we have a listing_id, fire a SILENT
  // priming request (no UI message inserted) so Gemini already has the
  // listing + comparables context before the user types anything.
  const silentPrimedRef = useRef(new Set());
  useEffect(() => {
    if (!isOpen || !listingIdForChat) return;
    if (silentPrimedRef.current.has(listingIdForChat)) return;
    silentPrimedRef.current.add(listingIdForChat);
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), 12000);
    fetch(`${backendUrl}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: ctrl.signal,
      body: JSON.stringify({
        message: `The user is currently viewing listing ID ${listingIdForChat}. Analyze the context and be ready to assist.`,
        listing_id: listingIdForChat,
        google_search: false,
      }),
    })
      .then((res) => res.body && res.body.getReader().read())  // drain first chunk then drop
      .catch(() => undefined)
      .finally(() => clearTimeout(tid));
  }, [isOpen, listingIdForChat, backendUrl]);

  // iter214 P4 — Request browser-notification permission when chat opens
  // (NOT on page load, per UX spec).
  useEffect(() => {
    if (!isOpen) return;
    if (typeof Notification === 'undefined') return;
    if (Notification.permission === 'default') {
      Notification.requestPermission().catch(() => undefined);
    }
  }, [isOpen]);

  // iter214 P4 — When the user opens the chat, clear unread badge + restore tab title.
  useEffect(() => {
    if (isOpen) {
      setUnreadBadge(0);
      if (typeof document !== 'undefined') document.title = originalTitleRef.current;
    }
  }, [isOpen]);

  // iter214 P4 — Multi-channel notification when an AI response arrives.
  // Fires only when the user is NOT actively focused on the chat window.
  const fireResponseNotification = useCallback((preview, isFr) => {
    try {
      // 1) Sound (only when tab not focused — respect quiet browsing)
      if (typeof document !== 'undefined' && document.hidden) {
        try {
          const AudioCtx = window.AudioContext || window.webkitAudioContext;
          if (AudioCtx) {
            const ctx = new AudioCtx();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.frequency.value = 880; // soft chime A5
            gain.gain.value = 0.05;
            osc.connect(gain).connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.25);
            setTimeout(() => ctx.close().catch(() => undefined), 400);
          }
        } catch { /* sound failed silently */ }
      }

      // 2) Browser notification
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        try {
          const n = new Notification(isFr ? 'BidVex IA a répondu' : 'BidVex AI replied', {
            body: (preview || '').slice(0, 60) + (preview && preview.length > 60 ? '…' : ''),
            icon: '/logo192.png',
            tag: 'bidvex-ai-response',
          });
          n.onclick = () => {
            window.focus();
            setIsOpen(true);
            n.close();
          };
        } catch { /* notification denied */ }
      }

      // 3) In-app toast — Sonner provider is already mounted globally.
      // Show only when chat is closed; when open the user already sees the
      // assistant bubble appear in-line.
      if (!isOpen) {
        try {
          toast.success(
            isFr ? '💬 Le concierge IA a répondu à votre question' : '💬 AI Concierge replied to your question',
            { duration: 5000 },
          );
        } catch { /* sonner not mounted */ }
      }
      window.dispatchEvent(new CustomEvent('bidvex:ai-reply', { detail: { preview, isFr } }));

      // 4) Vibration (mobile)
      if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
        try { navigator.vibrate([200, 100, 200]); } catch { /* unsupported */ }
      }

      // 5) Tab title change when user on another tab
      if (typeof document !== 'undefined' && document.hidden) {
        document.title = isFr ? '💬 Nouvelle réponse — BidVex' : '💬 New reply — BidVex';
        // Restore when user comes back
        const restore = () => {
          if (!document.hidden) {
            document.title = originalTitleRef.current;
            document.removeEventListener('visibilitychange', restore);
          }
        };
        document.addEventListener('visibilitychange', restore);
      }

      // 6) Chat-icon badge (only when chat closed)
      if (!isOpen) setUnreadBadge((c) => c + 1);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn('[AIAssistant] notification fire failed:', err);
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    // iter239 Mission 4 — Allocate a stable session_id at first send so
    // every turn in this conversation lands on the same persisted doc.
    let sid = sessionId;
    if (!sid) {
      sid = (typeof crypto !== 'undefined' && crypto.randomUUID)
        ? crypto.randomUUID()
        : `sess-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      persistSessionId(sid);
    }

    const userMessage = input;
    const lang = (navigator.language || 'en').startsWith('fr') ? 'fr' : 'en';
    const isFr = lang === 'fr';
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage, rich_content: null }]);
    setIsLoading(true);

    // iter214 P4 — IMMEDIATE acknowledgment (< 800 ms). This is a pure UI state
    // change — no backend call. Tagged with `ack: true` so we can replace it
    // when the real response arrives.
    const ackId = ++acknowledgmentIdRef.current;
    const ackContent = isFr
      ? '🔍 Je recherche la meilleure réponse pour vous… Je vous notifierai dès que je réponds.'
      : '🔍 Searching for the best answer for you… I\'ll notify you as soon as I respond.';
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: ackContent, rich_content: null, ack: true, ackId },
    ]);

    // After 15 s of no response, upgrade the ack to the "still processing" copy.
    const stillProcessingTimer = setTimeout(() => {
      const longCopy = isFr
        ? "⏳ Notre IA traite votre demande. Cela peut prendre un moment pour les questions complexes. Nous vous notifierons dès que nous aurons une réponse — vous pouvez naviguer sur la plateforme en attendant."
        : "⏳ Our AI is processing your request. This may take a moment for complex questions. We'll notify you the second we have an answer — feel free to browse the platform while you wait.";
      setMessages((prev) => prev.map((m) =>
        m.ack && m.ackId === ackId ? { ...m, content: longCopy } : m
      ));
    }, 15000);

    // iter211 — optimistically clear the degraded banner when the user retries
    if (serviceDegraded) setServiceDegraded(false);

    // iter280 — Detect the current "surface" (public marketplace,
    // authenticated dashboard, admin control panel, or listing detail)
    // so the same unified assistant can adjust its tone + escalation
    // affordances per route. This replaces the previous iter277
    // approach of forking off into a separate dashboard-only widget.
    const _detectSurface = () => {
      if (typeof window === 'undefined') return 'public';
      const p = (window.location.pathname || '').toLowerCase();
      if (p.startsWith('/admin')) return 'admin';
      if (p.startsWith('/seller/dashboard') || p.startsWith('/seller-dashboard')
          || p.startsWith('/buyer/dashboard')  || p.startsWith('/buyer-dashboard')
          || p.startsWith('/facility/dashboard')) {
        return 'dashboard';
      }
      if (p.startsWith('/admin')) return 'admin';
      if (listingIdForChat) return 'listing_detail';
      return 'public';
    };
    const _activeSurface = _detectSurface();

    const buildBody = () => JSON.stringify({
      // iter235 — Direct google-genai streaming endpoint (/api/chat/stream)
      // expects { message, extra_context, google_search, listing_id }.
      // iter236 Mission 3 — Always forward listing_id so the backend can
      // inject current_viewed_listing + market_comparables when present.
      // iter239 Mission 4 — Forward session_id so the backend can up-sert
      // the persistent ai_chat_sessions doc (anonymous users are ignored
      // server-side).
      message: userMessage,
      google_search: true,
      listing_id: listingIdForChat || null,
      session_id: sid || null,
      extra_context: [
        `Active UI language: ${lang === 'fr' ? 'French (fr)' : 'English (en)'}.`,
        // iter280 — Surface hint lets the model adapt its tone for
        // dashboards (operational answers, link to admin/seller flows)
        // vs. public marketplace (lead-friendly + onboarding-focused).
        `Active UI surface: ${_activeSurface}.`,
        'Recent conversation (most recent last):',
        ...messages.slice(-10).map((m) => `- ${m.role}: ${(m.content || '').slice(0, 280)}`),
      ].join('\n'),
    });

    // iter235 — Streaming reader. Reads UTF-8 chunks from /api/chat/stream and
    // progressively appends them to the assistant message. The ack message is
    // converted in-place into the live streaming message as soon as the first
    // chunk arrives so the user sees the "typing" effect immediately.
    const streamOnce = async (timeoutMs) => {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const ctrl = new AbortController();
      // iter279 — Expose controller so the Stop button can call abort().
      activeStreamCtrlRef.current = ctrl;
      const tid = setTimeout(() => ctrl.abort(), timeoutMs);
      let assembled = '';
      let convertedAck = false;
      try {
        const res = await fetch(`${backendUrl}/chat/stream`, {
          method: 'POST', headers, signal: ctrl.signal, body: buildBody(),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (!res.body) throw new Error('No response body (streaming unsupported)');
        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const piece = decoder.decode(value, { stream: true });
          if (!piece) continue;
          assembled += piece;
          // Replace the "searching…" ack on first real chunk; thereafter
          // mutate the existing streaming bubble in place.
          if (!convertedAck) {
            convertedAck = true;
            setMessages((prev) => {
              const out = prev.filter((m) => !(m.ack && m.ackId === ackId));
              return [
                ...out,
                { role: 'assistant', content: assembled, rich_content: null, streaming: true, streamId: ackId },
              ];
            });
          } else {
            setMessages((prev) => prev.map((m) =>
              m.streamId === ackId ? { ...m, content: assembled } : m
            ));
          }
        }
        // Flush trailing decoder bytes
        const tail = decoder.decode();
        if (tail) {
          assembled += tail;
          setMessages((prev) => prev.map((m) =>
            m.streamId === ackId ? { ...m, content: assembled } : m
          ));
        }
        if (!assembled.trim()) throw new Error('empty stream');
        return assembled;
      } finally {
        clearTimeout(tid);
        // iter279 — Always release the controller ref so a follow-up
        // turn doesn't try to abort the wrong fetch.
        if (activeStreamCtrlRef.current === ctrl) {
          activeStreamCtrlRef.current = null;
        }
      }
    };

    try {
      let assembled;
      try {
        assembled = await streamOnce(45000);
      } catch (firstErr) {
        // eslint-disable-next-line no-console
        console.warn('[AIAssistant] first stream attempt failed, retrying once:', firstErr?.message);
        await new Promise((r) => setTimeout(r, 800));
        // Remove the partial (failed) streaming bubble before retrying.
        setMessages((prev) => prev.filter((m) => m.streamId !== ackId));
        assembled = await streamOnce(60000);
      }
      clearTimeout(stillProcessingTimer);
      setServiceDegraded(false);
      // iter321 — Intercept the [[BIDVEX_ESCALATION]]…[[/BIDVEX_ESCALATION]]
      // marker before finalizing the bubble. Posts to /api/support/escalate,
      // strips the marker from the visible content, and appends a system
      // confirmation bubble. Fire-and-forget — UX never blocks on this.
      const _ESCALATION_RE = /\[\[BIDVEX_ESCALATION\]\]([\s\S]*?)\[\[\/BIDVEX_ESCALATION\]\]/;
      const _strip = (txt) => (txt || '').replace(_ESCALATION_RE, '').trim();
      const visibleContent = _strip(assembled);
      // Finalize the streaming bubble (drop the streaming flag) WITH the
      // marker stripped from the rendered text.
      setMessages((prev) => prev.map((m) =>
        m.streamId === ackId
          ? { ...m, content: visibleContent, streaming: false, streamId: undefined }
          : m
      ));
      // Out-of-band: fire the escalation POST if the marker was present.
      try {
        const match = _ESCALATION_RE.exec(assembled);
        if (match && token) {
          let payload = null;
          try { payload = JSON.parse((match[1] || '').trim()); } catch { /* malformed */ }
          if (payload && payload.problem) {
            const recent = (messages || []).slice(-12).map((mm) => ({
              role:    mm.role,
              content: _strip(mm.content),
              ts:      mm.ts || new Date().toISOString(),
            })).filter((mm) => mm.content);
            fetch(`${backendUrl}/support/escalate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify({
                problem:    String(payload.problem || '').slice(0, 1500),
                details:    String(payload.details || '').slice(0, 2500),
                language:   payload.language || (isFr ? 'fr' : 'en'),
                transcript: recent,
                session_id: sessionId || null,
                page_url:   typeof window !== 'undefined' ? window.location.pathname : null,
              }),
            }).then((r) => r.ok ? r.json() : null).then((json) => {
              if (!json || !json.ticket_id) return;
              const shortId = String(json.ticket_id).slice(0, 8);
              setMessages((prev) => [
                ...prev,
                {
                  role: 'assistant',
                  content: isFr
                    ? `✅ Demande créée : #${shortId} · Un agent vous contactera sous peu.`
                    : `✅ Ticket created: #${shortId} · An agent will reach out shortly.`,
                  rich_content: null,
                  escalation_ticket_id: json.ticket_id,
                },
              ]);
            }).catch(() => { /* silent — user can retry via Talk to a human */ });
          }
        }
      } catch (e) { /* never let the escalation hook break the chat */ }
      fireResponseNotification(visibleContent, isFr);
    } catch (e) {
      // iter279 — When the user clicks Stop mid-stream the fetch
      // throws AbortError. That's a deliberate cancellation, not a
      // failure — finalize the partial bubble in place and DO NOT
      // surface the giant "service unavailable" red CTA.
      const wasUserAbort = e?.name === 'AbortError' && !activeStreamCtrlRef.current;
      // eslint-disable-next-line no-console
      console.error('[AIAssistant] both attempts failed:', e?.message);
      clearTimeout(stillProcessingTimer);
      if (wasUserAbort) {
        setMessages((prev) => prev.map((m) => (
          m.streamId === ackId
            ? { ...m, streaming: false, streamId: undefined, partial: true }
            : m
        )));
      } else {
        setServiceDegraded(true);
        setMessages((prev) => {
          // iter235 — also drop any partial streaming bubble produced by a failed retry.
          const out = prev.filter((m) => !(m.ack && m.ackId === ackId) && m.streamId !== ackId);
          return [
            ...out,
            {
              role: 'assistant',
              content: 'Service temporarily unavailable. Please retry in a moment, or email support@bidvex.com for immediate help.\n\nService temporairement indisponible. Veuillez réessayer dans un instant ou écrire à support@bidvex.com pour de l\'aide immédiate.',
              rich_content: {
                has_rich_content: true,
                action_buttons: [
                  { text: 'Email Support / Contacter le support', action: 'email', url: 'support@bidvex.com', icon: 'mail', style: 'primary' },
                ],
              },
            },
          ];
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  // iter279 — User-initiated stop. Aborts the active stream's
  // AbortController; the partial text already on screen remains
  // visible and is finalized in the catch above.
  const handleStop = () => {
    const ctrl = activeStreamCtrlRef.current;
    if (!ctrl) return;
    // Clear ref BEFORE calling abort so the catch handler's
    // `!activeStreamCtrlRef.current` check identifies this as a
    // user-initiated abort vs. an internal timeout abort.
    activeStreamCtrlRef.current = null;
    try { ctrl.abort(); } catch { /* noop */ }
  };

  const handleActionButton = (action, url) => {
    if (action === 'navigate' && url) {
      navigate(url);
      setIsOpen(false);
    } else if (action === 'open_url' && url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    } else if (action === 'email' && url) {
      window.location.href = `mailto:${url}`;
    }
  };

  // iter239 Mission 4 — Chat history helpers.
  const fetchHistory = useCallback(async () => {
    if (!token) {
      setHistorySessions([]);
      return;
    }
    setHistoryLoading(true);
    try {
      const res = await fetch(`${backendUrl}/chat/history?page=1&per_page=20`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setHistorySessions(Array.isArray(data.sessions) ? data.sessions : []);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('[AIAssistant] fetchHistory failed:', e?.message);
      setHistorySessions([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [backendUrl, token]);

  const loadSession = useCallback(async (sid) => {
    if (!token || !sid) return;
    try {
      const res = await fetch(`${backendUrl}/chat/history/${sid}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const msgs = Array.isArray(data.messages) ? data.messages : [];
      setMessages(msgs.map((m) => ({
        role: m.role,
        content: m.content || '',
        rich_content: null,
      })));
      persistSessionId(sid);
      // Mark read silently.
      fetch(`${backendUrl}/chat/mark-read/${sid}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => undefined);
      setHistoryOpen(false);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('[AIAssistant] loadSession failed:', e?.message);
      toast.error('Could not load that conversation.');
    }
  }, [backendUrl, token, persistSessionId]);

  const deleteSession = useCallback(async (sid) => {
    if (!token || !sid) return;
    try {
      const res = await fetch(`${backendUrl}/chat/history/${sid}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setHistorySessions((prev) => prev.filter((s) => s.session_id !== sid));
      if (sid === sessionId) {
        // The active conversation was deleted — reset to a fresh chat.
        try { localStorage.removeItem('bidvex.chat.session_id'); } catch { /* ignore */ }
        setSessionId('');
        setMessages([{
          role: 'assistant',
          content: 'Welcome to BidVex! I am the BidVex AI Core, here to help with bidding, account questions, and platform guidance. How may I assist you today?',
          rich_content: null,
        }]);
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('[AIAssistant] deleteSession failed:', e?.message);
      toast.error('Could not delete that conversation.');
    }
  }, [backendUrl, token, sessionId]);

  // iter279 — Cleanup: if the component unmounts (route change /
  // hot reload) while a stream is in flight, abort the fetch so the
  // socket isn't leaked.
  useEffect(() => () => {
    const ctrl = activeStreamCtrlRef.current;
    if (ctrl) {
      activeStreamCtrlRef.current = null;
      try { ctrl.abort(); } catch { /* noop */ }
    }
  }, []);

  const startNewChat = useCallback(() => {
    try { localStorage.removeItem('bidvex.chat.session_id'); } catch { /* ignore */ }
    setSessionId('');
    setMessages([{
      role: 'assistant',
      content: 'Welcome to BidVex! I am the BidVex AI Core, here to help with bidding, account questions, and platform guidance. How may I assist you today?',
      rich_content: null,
    }]);
    setHistoryOpen(false);
  }, []);

  // Auto-load history list when the panel opens.
  useEffect(() => {
    if (historyOpen && token) {
      fetchHistory();
    }
  }, [historyOpen, token, fetchHistory]);


  const getActionIcon = (icon) => {
    const iconProps = { className: 'h-4 w-4 mr-2' };
    switch (icon) {
      case 'shield-check': return <ShieldCheck {...iconProps} />;
      case 'credit-card': return <CreditCard {...iconProps} />;
      case 'package': return <Package {...iconProps} />;
      case 'help-circle': return <HelpCircle {...iconProps} />;
      case 'mail': return <Mail {...iconProps} />;
      default: return null;
    }
  };

  return (
    <>
      {!isOpen && (
        <Button
          onClick={handleFabClick}
          onMouseDown={onPointerDown}
          onMouseMove={onPointerMove}
          onMouseUp={onPointerUp}
          onMouseLeave={onPointerUp}
          onTouchStart={onPointerDown}
          onTouchMove={onPointerMove}
          onTouchEnd={onPointerUp}
          className="rounded-full w-14 h-14 sm:w-16 sm:h-16 text-white border border-white/20 shadow-2xl transition-shadow hover:scale-110 hover:shadow-cyan-500/50 hover:border-white/40 select-none touch-none cursor-grab active:cursor-grabbing"
          style={{
            position: 'fixed',
            left: fabPos.x,
            top: fabPos.y,
            zIndex: 1000,
            backdropFilter: 'blur(8px)',
            background: 'rgba(37, 99, 235, 0.9)',
            touchAction: 'none',
          }}
          data-testid="ai-assistant-btn"
          aria-label="Open BidVex AI Core — drag to reposition"
          title="Tap to chat. Drag to reposition."
        >
          <MessageCircle className="h-7 w-7 pointer-events-none" />
          <GripVertical className="absolute -top-1 -right-1 h-3 w-3 text-white/60 pointer-events-none" aria-hidden="true" />
          {/* iter214 P4 — Unread-badge on FAB when AI replied while chat is closed */}
          {unreadBadge > 0 && (
            <span
              className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 bg-rose-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center shadow-lg pointer-events-none"
              data-testid="ai-assistant-unread-badge"
            >
              {unreadBadge > 9 ? '9+' : unreadBadge}
            </span>
          )}
        </Button>
      )}

      {isOpen && (
        <>
          {/* Mobile Bottom Sheet Backdrop */}
          <div
            className="md:hidden fixed inset-0 bg-black/50 z-[999] backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
            data-testid="ai-assistant-backdrop"
          />

          {/* Chatbot Card — also sits above the mobile bottom nav */}
          <div
            className="fixed z-[1000] flex flex-col rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-white dark:bg-slate-900"
            style={{
              left: '12px',
              right: '12px',
              bottom: `calc(${MOBILE_NAV_HEIGHT}px + env(safe-area-inset-bottom, 0px) + ${FAB_GAP}px)`,
              maxHeight: `calc(100vh - ${MOBILE_NAV_HEIGHT}px - env(safe-area-inset-bottom, 0px) - 64px)`,
            }}
          >
            {/* Header */}
            <div className="p-4 flex justify-between items-center bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] text-white flex-shrink-0">
              <div className="flex items-center gap-2">
                {/* iter239 Mission 4 — History toggle. Only meaningful when logged in. */}
                {token && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setHistoryOpen((v) => !v)}
                    className="text-white hover:bg-white/20 rounded-full h-8 w-8"
                    aria-label={historyOpen ? 'Close history' : 'Open history'}
                    title={historyOpen ? 'Close history' : 'Conversation history'}
                    data-testid="ai-assistant-history-toggle"
                  >
                    {historyOpen ? <ChevronLeft className="h-4 w-4" /> : <History className="h-4 w-4" />}
                  </Button>
                )}
                <div>
                  <h3 className="font-bold text-lg text-white">BidVex AI Core</h3>
                  <p className="text-xs text-white/90">Your Luxury Auction Specialist</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {/* iter321 — Manual "Talk to a human" fallback (always available
                    for logged-in users). Bypasses the AI and POSTs directly to
                    /api/support/escalate so a ticket is guaranteed even if the
                    AI is misbehaving. */}
                {token && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setManualEscalationOpen(true)}
                    className="text-white hover:bg-white/20 rounded-full h-8 w-8"
                    aria-label="Talk to a human"
                    title="Talk to a human"
                    data-testid="ai-assistant-talk-human"
                  >
                    <LifeBuoy className="h-4 w-4" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsOpen(false)}
                  className="text-white hover:bg-white/20 rounded-full"
                  aria-label="Close"
                  data-testid="ai-assistant-close-btn"
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </div>

            {/* iter239 Mission 4 — Slide-in history panel. Renders OVER the
                messages region when toggled so the chat card stays the
                same size on mobile. */}
            {historyOpen && (
              <div
                className="absolute inset-x-0 top-[72px] bottom-[88px] bg-white dark:bg-slate-900 z-10 flex flex-col border-t border-gray-200 dark:border-gray-700"
                data-testid="ai-assistant-history-panel"
              >
                <div className="px-4 py-3 flex items-center justify-between border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-800">
                  <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">Conversations</span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={startNewChat}
                    className="h-7 text-xs"
                    data-testid="ai-assistant-new-chat-btn"
                  >
                    + New Chat
                  </Button>
                </div>
                <div className="flex-1 overflow-y-auto">
                  {!token ? (
                    <div className="p-6 text-center text-sm text-slate-500">
                      Sign in to keep your conversation history.
                    </div>
                  ) : historyLoading ? (
                    <div className="p-6 text-center text-sm text-slate-500" data-testid="ai-history-loading">
                      Loading conversations…
                    </div>
                  ) : historySessions.length === 0 ? (
                    <div className="p-6 text-center text-sm text-slate-500" data-testid="ai-history-empty">
                      No previous conversations yet. Start chatting and your history will appear here.
                    </div>
                  ) : (
                    <ul className="divide-y divide-gray-100 dark:divide-gray-800">
                      {historySessions.map((s) => {
                        const isActive = s.session_id === sessionId;
                        const updated = s.updated_at ? new Date(s.updated_at).toLocaleString() : '';
                        return (
                          <li
                            key={s.session_id}
                            className={`group p-3 flex items-start gap-3 hover:bg-gray-50 dark:hover:bg-slate-800 cursor-pointer ${
                              isActive ? 'bg-cyan-50 dark:bg-cyan-900/20' : ''
                            }`}
                            onClick={() => loadSession(s.session_id)}
                            data-testid={`ai-history-session-${s.session_id}`}
                          >
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-slate-900 dark:text-slate-100 truncate">
                                {s.preview || 'New conversation'}
                              </p>
                              <p className="text-xs text-slate-500 mt-0.5">{updated}</p>
                              {!s.is_read && (
                                <span className="inline-block mt-1 w-2 h-2 rounded-full bg-cyan-500" aria-label="unread" />
                              )}
                            </div>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7 text-slate-400 hover:text-rose-500 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => { e.stopPropagation(); deleteSession(s.session_id); }}
                              aria-label="Delete conversation"
                              data-testid={`ai-history-delete-${s.session_id}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </div>
            )}

            {/* Degraded service banner */}
            {serviceDegraded && (
              <div
                className="px-4 py-2 bg-amber-50 dark:bg-amber-900/30 border-b border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200 text-xs flex-shrink-0"
                data-testid="ai-degraded-banner"
              >
                <span className="font-semibold">⚠ Service degraded.</span> Some replies may fail. Email <a href="mailto:support@bidvex.com" className="underline">support@bidvex.com</a> for urgent help.
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-slate-800 min-h-0">
              {messages.map((msg, idx) => (
                <div key={idx}>
                  <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] rounded-2xl p-3 shadow-md ${
                        msg.role === 'user'
                          ? 'bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] text-white'
                          : 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border border-gray-200 dark:border-gray-700'
                      }`}
                    >
                      <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                        {msg.content}
                        {/* iter279 — Pulsing typewriter cursor on the
                            active streaming bubble. Mirrors the
                            iter278 dashboard widget UX. */}
                        {msg.streaming && (
                          <span
                            className="inline-block w-1.5 h-3.5 ml-0.5 align-middle bg-[#06B6D4] animate-pulse"
                            data-testid="ai-core-stream-cursor"
                          />
                        )}
                      </p>
                      {/* iter279 — "(partial)" badge when the user
                          stops a stream mid-flight. */}
                      {msg.partial && (
                        <p
                          className="text-[10px] mt-1 text-rose-500"
                          data-testid={`ai-core-msg-partial-${idx}`}
                        >
                          · partial / partiel
                        </p>
                      )}
                    </div>
                  </div>
                  {msg.rich_content?.has_rich_content && msg.rich_content.action_buttons?.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2 justify-start ml-2">
                      {msg.rich_content.action_buttons.map((btn, btnIdx) => (
                        <Button
                          key={btnIdx}
                          onClick={() => handleActionButton(btn.action, btn.url)}
                          variant={btn.style === 'primary' ? 'default' : 'outline'}
                          size="sm"
                          className={
                            btn.style === 'primary'
                              ? 'bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0 shadow-md'
                              : 'border-[#06B6D4] text-[#1E3A8A] hover:bg-[#06B6D4]/10'
                          }
                        >
                          {getActionIcon(btn.icon)}
                          {btn.text}
                        </Button>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {/* Animated typing indicator (instant feedback while waiting on the LLM) */}
              {isLoading && (
                <div className="flex justify-start" data-testid="ai-typing-indicator">
                  <div className="bg-white dark:bg-gray-800 rounded-2xl px-4 py-3 shadow-sm border border-gray-200 dark:border-gray-700 flex items-center gap-1">
                    <span className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t bg-white dark:bg-gray-800 flex-shrink-0">
              <div className="flex gap-2">
                <Input
                  placeholder="Ask me anything about BidVex..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                  disabled={isLoading}
                  className="flex-1 border-gray-300 focus:border-[#06B6D4] focus:ring-[#06B6D4] text-slate-900 dark:text-slate-100"
                  data-testid="ai-assistant-input"
                />
                <Button
                  onClick={isLoading ? handleStop : handleSend}
                  disabled={!isLoading && !input.trim()}
                  className={isLoading
                    ? "bg-rose-600 hover:bg-rose-700 text-white border-0 px-4 flex-shrink-0"
                    : "bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0 px-4 flex-shrink-0"}
                  data-testid={isLoading ? "ai-core-stop" : "ai-assistant-send-btn"}
                  aria-label={isLoading ? "Stop generating" : "Send message"}
                >
                  {isLoading ? <Square className="h-4 w-4" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
                Powered by Gemini 2.5 Flash &bull; Available 24/7
              </p>
            </div>
          </div>
        </>
      )}

      {/* iter321 — Manual "Talk to a human" modal (escalation fallback) */}
      {manualEscalationOpen && (
        <div
          className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          data-testid="manual-escalation-modal"
          onClick={(e) => { if (e.target === e.currentTarget) setManualEscalationOpen(false); }}
        >
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
            <div className="px-5 py-4 bg-gradient-to-r from-rose-600 to-rose-700 text-white flex items-center gap-2">
              <LifeBuoy className="w-5 h-5" />
              <div className="leading-tight flex-1">
                <div className="text-sm font-bold">Talk to a Human</div>
                <div className="text-[10px] opacity-90">A BidVex agent will reach out shortly.</div>
              </div>
              <button
                type="button"
                onClick={() => setManualEscalationOpen(false)}
                className="p-1.5 rounded-md hover:bg-white/15"
                data-testid="manual-escalation-close"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                  1. What is the problem? *
                </label>
                <textarea
                  rows={3}
                  value={manualProblem}
                  onChange={(e) => setManualProblem(e.target.value)}
                  placeholder="Briefly describe your problem…"
                  maxLength={1500}
                  className="mt-1 w-full rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-rose-500"
                  data-testid="manual-escalation-problem"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                  2. Details (order ID, email, listing URL…)
                </label>
                <textarea
                  rows={3}
                  value={manualDetails}
                  onChange={(e) => setManualDetails(e.target.value)}
                  placeholder="Any helpful account context…"
                  maxLength={2500}
                  className="mt-1 w-full rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-rose-500"
                  data-testid="manual-escalation-details"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-1">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setManualEscalationOpen(false)}
                  data-testid="manual-escalation-cancel"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={submitManualEscalation}
                  disabled={!manualProblem.trim() || manualSubmitting}
                  className="bg-rose-600 hover:bg-rose-700 text-white"
                  data-testid="manual-escalation-submit"
                >
                  {manualSubmitting
                    ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    : <LifeBuoy className="w-4 h-4 mr-2" />}
                  Create Ticket
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default AIAssistant;
