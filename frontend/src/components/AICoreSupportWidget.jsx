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
import { Sparkles, X, Send, Loader2, Trash2 } from 'lucide-react';
import API_BASE from '../config';
import axios from 'axios';

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
  //                 content: string, ts: iso, error?: boolean }
  const [messages, setMessages] = useState([]);
  const scrollRef = useRef(null);

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

  const sendMessage = useCallback(async () => {
    const text = draft.trim();
    if (!text || sending || !token) return;

    const userMsg = { role: 'user', content: text, ts: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setDraft('');
    setSending(true);
    try {
      const r = await axios.post(
        `${API_BASE}/support/chat`,
        { message: text, session_id: sessionId, language: i18n.language || 'en' },
        { headers: { Authorization: `Bearer ${token}` }, timeout: 25_000 },
      );
      const reply = r?.data?.response || '';
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: reply, ts: new Date().toISOString() },
      ]);
    } catch (err) {
      const detail =
        err?.response?.data?.detail
        || err?.response?.data?.message
        || err?.message
        || 'unknown_error';
      setMessages((prev) => [
        ...prev,
        {
          role: 'system',
          content: `${t('aiCore.errorPrefix')}: ${String(detail).slice(0, 200)}`,
          ts: new Date().toISOString(),
          error: true,
        },
      ]);
    } finally {
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
                <div className="whitespace-pre-wrap break-words">{m.content}</div>
                <div className={`text-[9px] mt-1 ${m.role === 'user' ? 'text-indigo-200' : 'text-slate-400'}`}>
                  {fmtTime(m.ts)}
                </div>
              </div>
            ))}
            {sending && (
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
                onClick={sendMessage}
                disabled={sending || !draft.trim()}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
                data-testid="ai-core-send"
                aria-label={t('aiCore.sendLabel')}
              >
                {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </div>
            <p className="text-[9px] text-slate-400 mt-1">
              {t('aiCore.footerHint')}
            </p>
          </div>
        </div>
      )}
    </>
  );
};

export default AICoreSupportWidget;
