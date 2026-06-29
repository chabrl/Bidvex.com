/**
 * iter277 — AI Core Support Widget.
 *
 * A floating chat bubble mounted globally inside the User Dashboard
 * (buyer + seller) and the entire Admin control panel.  Wired directly
 * to the JWT-protected `POST /api/support/chat` endpoint shipped in
 * iter276.
 *
 * NOT a refactor of the existing `components/AIAssistant.js` — that
 * widget powers the public-facing site-wide assistant.  This widget is
 * the *internal* "Ask AI Core" surface that's grounded in the iter275
 * canonical platform guide and only renders for logged-in users on the
 * authenticated dashboards / admin pages.
 *
 * Key features:
 *   • Floating action button (FAB) → expandable chat panel
 *   • LocalStorage persistence per-user — past chats survive reloads
 *     and tab closes; resets per session_id so a different user on the
 *     same browser doesn't see another user's transcript
 *   • Bilingual EN/FR — every placeholder, button label, and system
 *     alert flows through `t(...)` from react-i18next so the active
 *     locale state controls everything
 *   • Optimistic UI: user message appears instantly while the network
 *     round trip resolves
 *   • Empty-state with "what can I ask" hint cards
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Sparkles, X, Send, Loader2, Trash2, Square, LifeBuoy } from 'lucide-react';
import API_BASE from '../config';

const STORAGE_PREFIX = 'bidvex.ai_core_chat.v1';
const MAX_LOCAL_HISTORY = 30;   // hard cap so localStorage stays small

const fmtTime = (iso) => {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return '';
  }
};

const AICoreSupportWidget = () => {
  const { t, i18n } = useTranslation();
  const { user, token } = useAuth();

  // Per-user localStorage key — switching accounts on the same browser
  // does NOT leak the previous user's chat history.
  const storageKey = `${STORAGE_PREFIX}.${user?.id || 'anonymous'}`;

  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  // Each message: { role: 'user' | 'assistant' | 'system',
  //                 content: string, ts: iso, error?: boolean,
  //                 streaming?: bool, partial?: bool }
  const [messages, setMessages] = useState([]);
  const scrollRef = useRef(null);
  // iter278 — Hold the in-flight stream's AbortController so the user
  // (or an unmount) can cancel mid-stream without dangling fetches.
  const abortRef = useRef(null);

  // ── Load persisted history on mount / user change ───────────────────
  useEffect(() => {
    if (!user?.id) {
      setMessages([]);
      return;
    }
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setMessages(parsed.slice(-MAX_LOCAL_HISTORY));
          return;
        }
      }
    } catch {
      /* corrupted blob — start clean */
    }
    setMessages([]);
  }, [user?.id, storageKey]);

  // ── Persist whenever messages change ────────────────────────────────
  useEffect(() => {
    if (!user?.id) return;
    try {
      const trimmed = messages.slice(-MAX_LOCAL_HISTORY);
      window.localStorage.setItem(storageKey, JSON.stringify(trimmed));
    } catch {
      /* localStorage full / disabled — fail silently, in-memory works */
    }
  }, [messages, storageKey, user?.id]);

  // ── Scroll the message list to bottom on every update ───────────────
  useEffect(() => {
    if (!open) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, open, sending]);

  const sessionId = user?.id ? `user:${user.id}` : null;

  // iter278 — Parse a single SSE event block ("event: foo\ndata: {...}").
  // Returns `{ event, data }` or null when the block is malformed
  // (which we silently ignore — keepalive comments and blank
  // separators are normal in the protocol).
  const _parseSseBlock = (raw) => {
    let event = 'message';
    let data = '';
    for (const line of raw.split('\n')) {
      if (line.startsWith(':')) continue;     // SSE keepalive comment
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += (data ? '\n' : '') + line.slice(5).trim();
    }
    if (!data) return null;
    try {
      return { event, data: JSON.parse(data) };
    } catch {
      return { event, data: { raw: data } };
    }
  };

  // iter278 — Append a streaming chunk to the LAST assistant message.
  // We track the streaming bubble by `streaming: true` flag rather than
  // index so a concurrent `clearHistory` doesn't blow up.
  const _appendChunkToActiveStream = (chunkText) => {
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i -= 1) {
        if (next[i].streaming) {
          next[i] = { ...next[i], content: next[i].content + chunkText };
          return next;
        }
      }
      return prev;
    });
  };

  // iter278 — Mark the active streaming bubble as completed. When
  // `error=true` we set `partial=true` so the UI shows "(partial)" in
  // the timestamp row — matches the "displays the partially
  // accumulated text without throwing" robustness contract.
  // iter320 — On non-error finalization, scan the final content for a
  // BIDVEX_ESCALATION marker and, if found, fire the escalation API
  // + strip the marker from the visible bubble.
  const _finalizeActiveStream = ({ error = false, partial = false } = {}) => {
    let finalContent = null;
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i -= 1) {
        if (next[i].streaming) {
          finalContent = next[i].content;
          const visible = error ? next[i].content : _stripEscalationMarker(next[i].content);
          next[i] = {
            ...next[i],
            content: visible,
            streaming: false,
            partial,
            error: error || next[i].error,
          };
          return next;
        }
      }
      return prev;
    });
    if (!error && finalContent && ESCALATION_RE.test(finalContent)) {
      // Fire-and-forget; failures are silent (banner only on success).
      _maybeEmitEscalation(finalContent);
    }
  };

  // iter320 — Detect [[BIDVEX_ESCALATION]]…[[/BIDVEX_ESCALATION]] markers
  // emitted by the AI Core per the Live Support Escalation Protocol.
  // When found, POST the payload + the recent transcript to the
  // /api/support/escalate endpoint and surface a banner to the user.
  const ESCALATION_RE = /\[\[BIDVEX_ESCALATION\]\]([\s\S]*?)\[\[\/BIDVEX_ESCALATION\]\]/;

  const _stripEscalationMarker = (text) => (text || '').replace(ESCALATION_RE, '').trim();

  const _maybeEmitEscalation = useCallback(async (finalText) => {
    if (!finalText || !token) return false;
    const m = ESCALATION_RE.exec(finalText);
    if (!m) return false;
    let payload;
    try {
      payload = JSON.parse((m[1] || '').trim());
    } catch {
      return false;
    }
    if (!payload?.problem) return false;
    const recent = (messages || []).slice(-12).map((mm) => ({
      role:    mm.role,
      content: _stripEscalationMarker(mm.content),
      ts:      mm.ts,
    })).filter((mm) => mm.content);
    try {
      const r = await fetch(`${API_BASE}/support/escalate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          problem:    String(payload.problem || '').slice(0, 1500),
          details:    String(payload.details || '').slice(0, 2500),
          language:   payload.language || i18n.language || 'en',
          transcript: recent,
          session_id: sessionId,
          page_url:   typeof window !== 'undefined' ? window.location.pathname : null,
        }),
      });
      if (!r.ok) return false;
      const json = await r.json();
      const isFr = (i18n.language || 'en').startsWith('fr');
      setMessages((prev) => [
        ...prev,
        {
          role:    'system',
          content: (isFr ? '✅ Demande créée : #' : '✅ Ticket created: #')
                    + String(json.ticket_id || '').slice(0, 8)
                    + (isFr ? ' · Un agent vous contactera sous peu.'
                            : ' · An agent will reach out shortly.'),
          ts:      new Date().toISOString(),
          escalation_ticket_id: json.ticket_id,
        },
      ]);
      return true;
    } catch {
      return false;
    }
  }, [token, messages, sessionId, i18n.language]);

  // iter278 — User can interrupt mid-stream via the Stop button. The
  // partially streamed text remains on screen as a finalized bubble.
  const stopStream = useCallback(() => {
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch { /* noop */ }
    }
  }, []);

  // Clean up any in-flight stream when the widget unmounts.
  useEffect(() => () => {
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch { /* noop */ }
    }
  }, []);

  const sendMessage = useCallback(async () => {
    const text = draft.trim();
    if (!text || sending || !token) return;

    const userMsg = { role: 'user', content: text, ts: new Date().toISOString() };
    // Pre-create the assistant streaming bubble so the typewriter
    // begins rendering chunks IMMEDIATELY when the first event lands.
    const assistantPlaceholder = {
      role: 'assistant', content: '', ts: new Date().toISOString(), streaming: true,
    };
    setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);
    setDraft('');
    setSending(true);

    const controller = new AbortController();
    abortRef.current = controller;
    let receivedAnyChunk = false;

    try {
      const res = await fetch(`${API_BASE}/support/chat/stream`, {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message:    text,
          session_id: sessionId,
          language:   i18n.language || 'en',
        }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        // Fall back to a single error frame — surface what the
        // backend said where possible so the user has actionable info.
        let detail = `HTTP ${res.status}`;
        try {
          const j = await res.json();
          detail = j?.detail || j?.message || detail;
        } catch { /* ignore */ }
        throw new Error(detail);
      }

      // ── Stream consumer ──
      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      // SSE blocks are separated by a blank line — we accumulate raw
      // bytes until we find that boundary, then parse each block.
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const rawBlock = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const parsed = _parseSseBlock(rawBlock);
          if (parsed) {
            if (parsed.event === 'chunk' && parsed.data?.text) {
              receivedAnyChunk = true;
              _appendChunkToActiveStream(parsed.data.text);
            } else if (parsed.event === 'error') {
              // Server-side mid-stream failure — render an inline
              // system note AND mark the partial bubble as partial.
              const reason = parsed.data?.reason || 'stream_error';
              setMessages((prev) => [
                ...prev,
                {
                  role:    'system',
                  content: `${t('aiCore.errorPrefix')}: ${reason}`,
                  ts:      new Date().toISOString(),
                  error:   true,
                },
              ]);
              _finalizeActiveStream({ error: true, partial: receivedAnyChunk });
              // We continue the loop so the eventual `done` frame
              // still arrives cleanly — but the bubble is already
              // closed.
            } else if (parsed.event === 'done') {
              _finalizeActiveStream({ partial: false });
            }
          }
          boundary = buffer.indexOf('\n\n');
        }
      }

      // Stream ended cleanly without a `done` frame — finalize anyway.
      _finalizeActiveStream({ partial: !receivedAnyChunk });
    } catch (err) {
      // AbortController.abort() raises an AbortError — that's the user
      // explicitly stopping, not a failure. Everything else surfaces
      // as an inline error system message.
      const isAbort = err?.name === 'AbortError';
      if (!isAbort) {
        const detail = err?.message || 'unknown_error';
        setMessages((prev) => [
          ...prev,
          {
            role:    'system',
            content: `${t('aiCore.errorPrefix')}: ${String(detail).slice(0, 200)}`,
            ts:      new Date().toISOString(),
            error:   true,
          },
        ]);
      }
      _finalizeActiveStream({
        error:   !isAbort,
        partial: receivedAnyChunk,
      });
    } finally {
      abortRef.current = null;
      setSending(false);
    }
  }, [draft, sending, token, sessionId, i18n.language, t]);

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearHistory = () => {
    setMessages([]);
    try { window.localStorage.removeItem(storageKey); } catch { /* noop */ }
  };

  // iter321 — Manual escalation fallback. If the AI is misbehaving and
  // not emitting the [[BIDVEX_ESCALATION]] marker, the user can click
  // "Talk to a human" to open a 2-question modal that POSTs directly
  // to /api/support/escalate. Guaranteed-reliable path.
  const [manualOpen, setManualOpen] = useState(false);
  const [manualProblem, setManualProblem] = useState('');
  const [manualDetails, setManualDetails] = useState('');
  const [manualSubmitting, setManualSubmitting] = useState(false);

  const submitManualEscalation = useCallback(async () => {
    const problem = manualProblem.trim();
    const details = manualDetails.trim();
    if (!problem || !token || manualSubmitting) return;
    setManualSubmitting(true);
    const recent = (messages || []).slice(-12).map((mm) => ({
      role:    mm.role,
      content: _stripEscalationMarker(mm.content),
      ts:      mm.ts,
    })).filter((mm) => mm.content);
    try {
      const r = await fetch(`${API_BASE}/support/escalate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          problem:    problem.slice(0, 1500),
          details:    details.slice(0, 2500),
          language:   (i18n.language || 'en'),
          transcript: recent,
          session_id: sessionId,
          page_url:   typeof window !== 'undefined' ? window.location.pathname : null,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const json = await r.json();
      const isFr = (i18n.language || 'en').startsWith('fr');
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: `[${isFr ? 'Demande humaine' : 'Human request'}] ${problem}`, ts: new Date().toISOString() },
        {
          role:    'system',
          content: (isFr ? '✅ Demande créée : #' : '✅ Ticket created: #')
                    + String(json.ticket_id || '').slice(0, 8)
                    + (isFr ? ' · Un agent vous contactera sous peu.'
                            : ' · An agent will reach out shortly.'),
          ts:      new Date().toISOString(),
          escalation_ticket_id: json.ticket_id,
        },
      ]);
      setManualOpen(false);
      setManualProblem('');
      setManualDetails('');
    } catch (e) {
      const isFr = (i18n.language || 'en').startsWith('fr');
      setMessages((prev) => [
        ...prev,
        {
          role:    'system',
          content: (isFr
            ? '❌ Échec de la création du ticket. Veuillez réessayer ou écrire à support@bidvex.com.'
            : '❌ Could not create your ticket. Please retry or email support@bidvex.com.'),
          ts:      new Date().toISOString(),
          error:   true,
        },
      ]);
    } finally {
      setManualSubmitting(false);
    }
  }, [manualProblem, manualDetails, manualSubmitting, token, messages, sessionId, i18n.language]);

  // No widget for unauthenticated users — guards against bots / leaking
  // platform-internal P0 language to anonymous traffic.
  if (!user) return null;

  // ── Suggested-question prompt cards for the empty state ────────────
  const promptCards = [
    { key: 'vehicle-bid',  label: t('aiCore.promptVehicleBid') },
    { key: 'trial-coupon', label: t('aiCore.promptTrialCoupon') },
    { key: 'tax-profile',  label: t('aiCore.promptTaxProfile') },
    { key: 'storage-doc',  label: t('aiCore.promptStorageDoc') },
  ];

  return (
    <>
      {/* ── Floating action button ─────────────────────────────────── */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={t('aiCore.openLabel')}
          className="fixed bottom-24 md:bottom-6 right-6 z-50 group flex items-center gap-2 px-4 py-3 rounded-full
                     bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg
                     hover:shadow-xl transition-all hover:-translate-y-0.5
                     focus:outline-none focus:ring-4 focus:ring-indigo-300"
          data-testid="ai-core-fab"
        >
          <Sparkles className="w-5 h-5" />
          <span className="text-sm font-semibold whitespace-nowrap">
            {t('aiCore.openLabel')}
          </span>
        </button>
      )}

      {/* ── Chat panel ───────────────────────────────────────────── */}
      {open && (
        <div
          className="fixed bottom-24 md:bottom-6 right-2 md:right-6 z-50 w-[calc(100vw-1rem)] md:w-[400px]
                     max-h-[80vh] flex flex-col bg-white dark:bg-slate-900 rounded-2xl
                     border border-slate-200 dark:border-slate-700 shadow-2xl overflow-hidden"
          data-testid="ai-core-widget"
          role="dialog"
          aria-label={t('aiCore.title')}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5" />
              <div className="leading-tight">
                <div className="text-sm font-bold">{t('aiCore.title')}</div>
                <div className="text-[10px] opacity-90">{t('aiCore.subtitle')}</div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {/* iter321 — Manual "Talk to a human" fallback (always available) */}
              <button
                type="button"
                onClick={() => setManualOpen(true)}
                className="p-1.5 rounded-md hover:bg-white/15 transition"
                aria-label={t('aiCore.talkToHumanLabel', 'Talk to a human')}
                data-testid="ai-core-talk-human"
                title={t('aiCore.talkToHumanLabel', 'Talk to a human')}
              >
                <LifeBuoy className="w-4 h-4" />
              </button>
              {messages.length > 0 && (
                <button
                  type="button"
                  onClick={clearHistory}
                  className="p-1.5 rounded-md hover:bg-white/15 transition"
                  aria-label={t('aiCore.clearLabel')}
                  data-testid="ai-core-clear"
                  title={t('aiCore.clearLabel')}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-md hover:bg-white/15 transition"
                aria-label={t('aiCore.closeLabel')}
                data-testid="ai-core-close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Message list */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-3 py-3 space-y-2 bg-slate-50 dark:bg-slate-800/50"
            data-testid="ai-core-message-list"
          >
            {messages.length === 0 && (
              <div className="space-y-2" data-testid="ai-core-empty-state">
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  {t('aiCore.emptyStateLead')}
                </p>
                <div className="grid grid-cols-1 gap-1.5">
                  {promptCards.map((p) => (
                    <button
                      key={p.key}
                      type="button"
                      className="text-left text-xs px-3 py-2 rounded-md border border-slate-200 dark:border-slate-700
                                 bg-white dark:bg-slate-900 hover:border-indigo-400 hover:bg-indigo-50/40
                                 dark:hover:bg-indigo-900/20 transition"
                      onClick={() => setDraft(p.label)}
                      data-testid={`ai-core-suggestion-${p.key}`}
                    >
                      → {p.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`max-w-[90%] rounded-xl px-3 py-2 text-sm leading-snug
                            ${m.role === 'user'
                              ? 'ml-auto bg-indigo-600 text-white'
                              : m.error
                              ? 'mr-auto bg-rose-100 text-rose-900 border border-rose-200'
                              : 'mr-auto bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-700'}`}
                data-testid={`ai-core-msg-${m.role}-${idx}`}
              >
                <div className="whitespace-pre-wrap break-words">
                  {m.content}
                  {/* iter278 — typewriter cursor on the active streaming bubble */}
                  {m.streaming && (
                    <span
                      className="inline-block w-1.5 h-3.5 ml-0.5 align-middle bg-indigo-500 animate-pulse"
                      data-testid="ai-core-stream-cursor"
                    />
                  )}
                </div>
                <div className={`text-[9px] mt-1 ${m.role === 'user' ? 'text-indigo-200' : 'text-slate-400'}`}>
                  {fmtTime(m.ts)}
                  {m.partial && (
                    <span
                      className="ml-1 text-rose-500"
                      data-testid={`ai-core-msg-partial-${idx}`}
                    >
                      · {t('aiCore.partialLabel')}
                    </span>
                  )}
                </div>
              </div>
            ))}
            {/* iter278 — typing indicator only while we're streaming AND
                the active bubble hasn't received a chunk yet. Once
                chunks arrive, the typewriter cursor replaces it. */}
            {sending && !messages.some(
              (m) => m.streaming && m.content && m.content.length > 0,
            ) && (
              <div
                className="mr-auto bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700
                           rounded-xl px-3 py-2 text-xs text-slate-500 flex items-center gap-2"
                data-testid="ai-core-typing"
              >
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {t('aiCore.thinking')}
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="border-t border-slate-200 dark:border-slate-700 px-3 py-2 bg-white dark:bg-slate-900">
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={t('aiCore.placeholder')}
                rows={1}
                className="flex-1 resize-none border border-slate-300 dark:border-slate-600 rounded-md
                           px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500
                           bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                data-testid="ai-core-input"
                disabled={sending}
                maxLength={4000}
              />
              <Button
                type="button"
                onClick={sending ? stopStream : sendMessage}
                disabled={!sending && !draft.trim()}
                className={sending
                  ? "bg-rose-600 hover:bg-rose-700 text-white"
                  : "bg-indigo-600 hover:bg-indigo-700 text-white"}
                data-testid={sending ? "ai-core-stop" : "ai-core-send"}
                aria-label={sending ? t('aiCore.stopLabel') : t('aiCore.sendLabel')}
              >
                {sending ? <Square className="w-4 h-4" /> : <Send className="w-4 h-4" />}
              </Button>
            </div>
            <p className="text-[9px] text-slate-400 mt-1">
              {t('aiCore.footerHint')}
            </p>
          </div>
        </div>
      )}

      {/* iter321 — Manual "Talk to a human" modal (escalation fallback) */}
      {manualOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          data-testid="manual-escalation-modal"
          onClick={(e) => { if (e.target === e.currentTarget) setManualOpen(false); }}
        >
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
            <div className="px-5 py-4 bg-gradient-to-r from-rose-600 to-rose-700 text-white flex items-center gap-2">
              <LifeBuoy className="w-5 h-5" />
              <div className="leading-tight flex-1">
                <div className="text-sm font-bold">
                  {(i18n.language || 'en').startsWith('fr')
                    ? 'Parler à un humain'
                    : 'Talk to a Human'}
                </div>
                <div className="text-[10px] opacity-90">
                  {(i18n.language || 'en').startsWith('fr')
                    ? 'Un agent BidVex vous contactera sous peu.'
                    : 'A BidVex agent will reach out shortly.'}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setManualOpen(false)}
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
                  {(i18n.language || 'en').startsWith('fr')
                    ? '1. Quel est le problème ? *'
                    : '1. What is the problem? *'}
                </label>
                <textarea
                  rows={3}
                  value={manualProblem}
                  onChange={(e) => setManualProblem(e.target.value)}
                  placeholder={(i18n.language || 'en').startsWith('fr')
                    ? "Décrivez brièvement votre problème…"
                    : "Briefly describe your problem…"}
                  maxLength={1500}
                  className="mt-1 w-full rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-rose-500"
                  data-testid="manual-escalation-problem"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                  {(i18n.language || 'en').startsWith('fr')
                    ? '2. Détails (ID de commande, courriel, URL d\'annonce…)'
                    : '2. Details (order ID, email, listing URL…)'}
                </label>
                <textarea
                  rows={3}
                  value={manualDetails}
                  onChange={(e) => setManualDetails(e.target.value)}
                  placeholder={(i18n.language || 'en').startsWith('fr')
                    ? "Toute information de compte utile…"
                    : "Any helpful account context…"}
                  maxLength={2500}
                  className="mt-1 w-full rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-rose-500"
                  data-testid="manual-escalation-details"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-1">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setManualOpen(false)}
                  data-testid="manual-escalation-cancel"
                >
                  {(i18n.language || 'en').startsWith('fr') ? 'Annuler' : 'Cancel'}
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
                  {(i18n.language || 'en').startsWith('fr') ? 'Créer le ticket' : 'Create Ticket'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default AICoreSupportWidget;
