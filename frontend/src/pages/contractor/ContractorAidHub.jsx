/**
 * iter331 — Contractor Aid Hub
 *
 * A dedicated onboarding + operational reference page for contractors,
 * served at /contractor/aid. Combines:
 *   - 6 static workflow sections (commission, IVR, email, add-client,
 *     stripe, escalation) rendered from /api/contractor/aid/info.
 *   - A live BitVex AI chat (Gemini 3 Flash) powered by
 *     /api/contractor/aid/chat for interactive Q&A.
 *
 * Fully bilingual EN/FR. Server-enforced role gate (dialer_contractor +
 * admin only).
 */
import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  LifeBuoy, ChevronLeft, Send, Loader2, Bot, User as UserIcon,
  Sparkles, BookOpen, MessageCircle, AlertTriangle,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Textarea } from '../../components/ui/textarea';

const MAX_MESSAGE = 4000;

// Minimal markdown → JSX renderer: supports **bold**, `code`,
// - lists, headings (## / ###), and paragraphs.
function renderMarkdown(text) {
  if (!text) return null;
  const lines = String(text).split(/\r?\n/);
  const blocks = [];
  let listBuf = null;

  const flushList = () => {
    if (listBuf && listBuf.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="list-disc list-inside space-y-1 my-2 text-sm">
          {listBuf.map((item, i) => (
            <li key={i}>{renderInline(item)}</li>
          ))}
        </ul>,
      );
    }
    listBuf = null;
  };

  const renderInline = (s) => {
    const parts = [];
    let rest = s;
    let key = 0;
    const re = /(\*\*[^*]+\*\*|`[^`]+`)/;
    while (rest) {
      const m = rest.match(re);
      if (!m) { parts.push(rest); break; }
      const idx = m.index;
      if (idx > 0) parts.push(rest.slice(0, idx));
      const token = m[0];
      if (token.startsWith('**')) {
        parts.push(<strong key={`b-${key++}`}>{token.slice(2, -2)}</strong>);
      } else if (token.startsWith('`')) {
        parts.push(<code key={`c-${key++}`} className="px-1 py-0.5 bg-slate-100 rounded text-[12px]">{token.slice(1, -1)}</code>);
      }
      rest = rest.slice(idx + token.length);
    }
    return parts;
  };

  lines.forEach((rawLine, i) => {
    const line = rawLine.trimEnd();
    if (line.startsWith('### ')) {
      flushList();
      blocks.push(<h4 key={`h3-${i}`} className="text-base font-semibold mt-3 mb-1">{renderInline(line.slice(4))}</h4>);
    } else if (line.startsWith('## ')) {
      flushList();
      blocks.push(<h3 key={`h2-${i}`} className="text-lg font-bold mt-4 mb-1">{renderInline(line.slice(3))}</h3>);
    } else if (line.startsWith('- ')) {
      if (!listBuf) listBuf = [];
      listBuf.push(line.slice(2));
    } else if (line === '') {
      flushList();
    } else {
      flushList();
      blocks.push(<p key={`p-${i}`} className="text-sm leading-relaxed my-1">{renderInline(line)}</p>);
    }
  });
  flushList();
  return blocks;
}

function SectionCard({ section, fr, idx }) {
  return (
    <Card data-testid={`aid-section-${section.id}`} className="border-slate-200">
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-center gap-2 mb-2">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex-shrink-0">
            {idx + 1}
          </span>
          <h3 className="font-bold text-base sm:text-lg">
            {fr ? section.title_fr : section.title_en}
          </h3>
        </div>
        <div className="pl-9 text-slate-700">
          {renderMarkdown(fr ? section.body_fr : section.body_en)}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ContractorAidHub() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const { user, token, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [info, setInfo] = useState(null);
  const [loadingInfo, setLoadingInfo] = useState(true);
  const [error, setError] = useState(null);

  // Chat state
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const chatEndRef = useRef(null);

  // Initial load
  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/auth?next=/contractor/aid', { replace: true });
      return;
    }
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/contractor/aid/info`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setInfo(r.data);
      } catch (e) {
        if (cancelled) return;
        const status = e?.response?.status;
        setError({ code: status || 'unknown', message: e?.message });
      } finally {
        if (!cancelled) setLoadingInfo(false);
      }
    })();
    return () => { cancelled = true; };
  }, [authLoading, user, token, navigate]);

  // Scroll to bottom on new chat message
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, sending]);

  const sendMessage = async () => {
    const msg = (draft || '').trim();
    if (!msg) return;
    if (msg.length > MAX_MESSAGE) {
      toast.error(fr ? `Message trop long (max ${MAX_MESSAGE} caractères).` : `Message too long (max ${MAX_MESSAGE} chars).`);
      return;
    }
    setSending(true);
    setMessages((prev) => [...prev, { role: 'user', content: msg, ts: new Date().toISOString() }]);
    setDraft('');
    try {
      const r = await axios.post(
        `${API_BASE}/contractor/aid/chat`,
        {
          message: msg,
          session_id: sessionId || undefined,
          language: fr ? 'fr' : 'en',
        },
        { headers: { Authorization: `Bearer ${token}` }, timeout: 60000 },
      );
      const reply = r.data?.reply || (fr ? 'Aucune réponse.' : 'No reply.');
      if (r.data?.session_id) setSessionId(r.data.session_id);
      setMessages((prev) => [...prev, { role: 'assistant', content: reply, ts: r.data?.ts }]);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const errMsg = typeof detail === 'string' ? detail : (e?.message || 'AI error');
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: (fr ? `Désolé, l'assistant est indisponible : ${errMsg}` : `Sorry, the assistant is unavailable: ${errMsg}`), error: true },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ─── Render ───────────────────────────────────────────────────────
  if (authLoading || loadingInfo) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="contractor-aid-loading">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-3" />
        <span>{fr ? 'Chargement…' : 'Loading…'}</span>
      </div>
    );
  }

  if (error?.code === 403) {
    return (
      <div className="container mx-auto max-w-3xl py-12 px-4" data-testid="contractor-aid-403">
        <Card className="border-2 border-rose-300 bg-rose-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertTriangle className="h-6 w-6 text-rose-600 flex-shrink-0" />
            <div>
              <h2 className="font-semibold text-rose-900">
                {fr ? 'Accès refusé' : 'Access denied'}
              </h2>
              <p className="text-sm text-rose-800 mt-1">
                {fr
                  ? 'Ce hub est réservé aux contractants approuvés.'
                  : 'This hub is reserved for approved contractors.'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const sections = info?.sections || [];

  return (
    <div className="container mx-auto max-w-7xl py-4 sm:py-6 px-3 sm:px-4 space-y-4" data-testid="contractor-aid-page">
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="min-w-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/contractor/dashboard')}
            className="-ml-2 mb-1"
            data-testid="aid-back-btn"
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            {fr ? 'Retour' : 'Back'}
          </Button>
          <h1
            className="text-xl sm:text-2xl lg:text-3xl font-bold flex items-center gap-2"
            data-testid="aid-page-title"
          >
            <LifeBuoy className="h-6 w-6 sm:h-7 sm:w-7 text-amber-600 flex-shrink-0" />
            {fr ? 'Aide Contractant — BitVex AI' : 'Contractor Aid — BitVex AI'}
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {fr
              ? 'Tout ce que vous devez savoir pour piloter votre activité de contractant BidVex, plus un assistant IA en direct pour répondre à vos questions.'
              : 'Everything you need to know to run your BidVex contractor activity, plus a live AI assistant to answer your questions.'}
          </p>
        </div>
      </header>

      {/* 2-column layout: workflow sections (left) + AI chat (right) */}
      <div className="grid grid-cols-1 xl:grid-cols-[3fr_2fr] gap-4 sm:gap-6">
        {/* Workflow sections */}
        <div className="space-y-3 sm:space-y-4 min-w-0" data-testid="aid-sections-grid">
          <div className="flex items-center gap-2 px-1">
            <BookOpen className="h-5 w-5 text-indigo-600" />
            <h2 className="text-base sm:text-lg font-bold">
              {fr ? 'Guide opérationnel' : 'Operational Playbook'}
            </h2>
          </div>
          {sections.map((s, idx) => (
            <SectionCard key={s.id} section={s} fr={fr} idx={idx} />
          ))}
        </div>

        {/* AI Chat */}
        <div className="min-w-0 xl:sticky xl:top-4 xl:self-start" data-testid="aid-chat-panel">
          <Card className="border-2 border-indigo-200 bg-white shadow-lg">
            <CardContent className="p-0">
              <div
                className="p-4 border-b flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-cyan-600 text-white rounded-t-lg"
                data-testid="aid-chat-header"
              >
                <Sparkles className="h-5 w-5" />
                <h2 className="font-bold text-base sm:text-lg flex-1 min-w-0">
                  {fr ? 'BitVex AI — Assistant en direct' : 'BitVex AI — Live Assistant'}
                </h2>
                <span className="text-[10px] px-2 py-0.5 bg-white/20 rounded-full font-mono whitespace-nowrap">
                  {info?.model || 'gemini'}
                </span>
              </div>

              {/* Messages */}
              <div
                className="p-3 sm:p-4 h-[400px] sm:h-[480px] overflow-y-auto bg-slate-50"
                data-testid="aid-chat-messages"
              >
                {messages.length === 0 && (
                  <div
                    className="flex flex-col items-center justify-center h-full text-center px-2"
                    data-testid="aid-chat-empty"
                  >
                    <MessageCircle className="h-10 w-10 text-indigo-300 mb-3" />
                    <p className="text-sm font-semibold text-slate-700">
                      {fr ? 'Posez n\'importe quelle question opérationnelle.' : 'Ask any operational question.'}
                    </p>
                    <p className="text-xs text-slate-500 mt-1 max-w-xs">
                      {fr
                        ? 'Ex. : « Comment fonctionne le bonus du Top 5 ? » ou « Comment changer mon poste IVR ? »'
                        : 'Try: "How does the Top 5 bonus work?" or "How do I change my IVR extension?"'}
                    </p>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`mb-3 flex gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    data-testid={`aid-chat-msg-${i}`}
                  >
                    {m.role === 'assistant' && (
                      <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                        <Bot className="h-4 w-4 text-indigo-700" />
                      </div>
                    )}
                    <div
                      className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                        m.role === 'user'
                          ? 'bg-indigo-600 text-white'
                          : m.error
                          ? 'bg-rose-100 text-rose-900 border border-rose-300'
                          : 'bg-white border border-slate-200 text-slate-800'
                      }`}
                    >
                      {m.role === 'assistant' ? renderMarkdown(m.content) : <span className="whitespace-pre-wrap">{m.content}</span>}
                    </div>
                    {m.role === 'user' && (
                      <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
                        <UserIcon className="h-4 w-4 text-slate-600" />
                      </div>
                    )}
                  </div>
                ))}
                {sending && (
                  <div className="flex gap-2 justify-start" data-testid="aid-chat-typing">
                    <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                      <Bot className="h-4 w-4 text-indigo-700" />
                    </div>
                    <div className="bg-white border border-slate-200 rounded-2xl px-3 py-2 text-sm flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-slate-500">{fr ? 'BitVex réfléchit…' : 'BitVex is thinking…'}</span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Composer */}
              <div className="p-3 sm:p-4 border-t bg-white rounded-b-lg">
                <Textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={fr ? 'Posez votre question…' : 'Ask your question…'}
                  className="resize-none mb-2"
                  rows={3}
                  maxLength={MAX_MESSAGE}
                  disabled={sending}
                  data-testid="aid-chat-input"
                />
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] text-slate-400">
                    {draft.length} / {MAX_MESSAGE}
                  </span>
                  <Button
                    onClick={sendMessage}
                    disabled={sending || !draft.trim()}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white"
                    data-testid="aid-chat-send-btn"
                  >
                    {sending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Send className="h-4 w-4 mr-1" />}
                    {fr ? 'Envoyer' : 'Send'}
                  </Button>
                </div>
                <p className="text-[10px] text-slate-400 mt-2">
                  {fr
                    ? `Pour une assistance humaine, écrivez à ${info?.support_email || 'support@bidvex.com'}.`
                    : `For human support, email ${info?.support_email || 'support@bidvex.com'}.`}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
