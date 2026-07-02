/**
 * iter335 — AI Coach Sidebar
 *
 * Real-time coaching panel shown in the AdminDialer during an active
 * outbound contractor→client call. Renders JSON hints pushed by the
 * backend WebSocket at /api/ws/contractor-coaching/{call_log_id}.
 *
 * Bilingual — labels flip when `language_detected` in the incoming
 * hint changes. Client never sees this panel; it's contractor-only.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  Bot, Sparkles, AlertTriangle, TrendingUp, TrendingDown,
  MessageCircle, ArrowRight, ChevronDown, ChevronUp, Radio,
} from 'lucide-react';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const SENTIMENT_STYLE = {
  positive:   { color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', dot: 'bg-emerald-500' },
  interested: { color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', dot: 'bg-emerald-500' },
  neutral:    { color: 'text-slate-700',   bg: 'bg-slate-50',   border: 'border-slate-200',   dot: 'bg-slate-400' },
  resistant:  { color: 'text-orange-700',  bg: 'bg-orange-50',  border: 'border-orange-200',  dot: 'bg-orange-500' },
  negative:   { color: 'text-rose-700',    bg: 'bg-rose-50',    border: 'border-rose-200',    dot: 'bg-rose-500' },
};

const TONE_LABEL = {
  en: {
    getting_impatient:   'Getting impatient',
    confused:            'Confused',
    warming_up:          'Warming up ↑',
    about_to_disengage:  'About to disengage ↓',
  },
  fr: {
    getting_impatient:   'S\'impatiente',
    confused:            'Perplexe',
    warming_up:          'S\'échauffe ↑',
    about_to_disengage:  'Sur le point de raccrocher ↓',
  },
};

const COMPLIANCE_LABEL = {
  en: {
    bill_96_required:            'Bill 96 — French language required',
    broker_rule_applicable:      'Provincial broker rule applies',
    prohibited_claim_detected:   'Prohibited claim detected',
  },
  fr: {
    bill_96_required:            'Loi 96 — Français requis',
    broker_rule_applicable:      'Règle de courtier provinciale',
    prohibited_claim_detected:   'Affirmation interdite détectée',
  },
};

const LABELS = {
  en: {
    heading:       'AI Call Coach',
    live:          'LIVE',
    offline:       'Off',
    subscribed:    'Waiting for audio…',
    degraded:      'AI coaching temporarily unavailable — call continues normally.',
    failed:        'AI coaching failed to start — call continues normally.',
    sessionEnded:  'AI session ended — call continues normally.',
    clientSentiment: 'Client sentiment',
    tone:          'Tone',
    tip:           'Coaching tip',
    nextLine:      'Suggested next line',
    compliance:    'Compliance',
    complianceNone:'None',
    lang:          'Language',
    minimize:      'Minimize',
    expand:        'Expand',
    waiting:       'Waiting for first AI hint (usually 7–15 s)…',
  },
  fr: {
    heading:       'Coach IA d\'appel',
    live:          'EN DIRECT',
    offline:       'Hors ligne',
    subscribed:    'En attente de l\'audio…',
    degraded:      'Coaching IA momentanément indisponible — l\'appel se poursuit normalement.',
    failed:        'Le coaching IA n\'a pas pu démarrer — l\'appel se poursuit normalement.',
    sessionEnded:  'Session IA terminée — l\'appel se poursuit normalement.',
    clientSentiment: 'Humeur du client',
    tone:          'Ton',
    tip:           'Conseil du coach',
    nextLine:      'Prochaine réplique suggérée',
    compliance:    'Conformité',
    complianceNone:'Aucun',
    lang:          'Langue',
    minimize:      'Réduire',
    expand:        'Agrandir',
    waiting:       'En attente du premier conseil IA (généralement 7 à 15 s)…',
  },
};

export default function AICoachSidebar({ callLogId, token, apiBase }) {
  const [aiStatus, setAiStatus] = useState('offline'); // offline|subscribed|active|degraded|failed|session_ended
  const [lastHint, setLastHint] = useState(null);
  const [hintCount, setHintCount] = useState(0);
  const [minimized, setMinimized] = useState(false);
  const wsRef = useRef(null);

  const lang = (lastHint?.language_detected === 'fr') ? 'fr' : 'en';
  const L = LABELS[lang];

  useEffect(() => {
    if (!callLogId || !token) return;
    const wsBase = (apiBase || '').replace(/^https?/, apiBase.startsWith('https') ? 'wss' : 'ws');
    const url = `${wsBase}/ws/contractor-coaching/${callLogId}?token=${encodeURIComponent(token)}`;

    let closed = false;
    let backoff = 800;
    let ws;
    const connect = () => {
      if (closed) return;
      try {
        ws = new WebSocket(url);
        wsRef.current = ws;
      } catch (e) {
        return;
      }
      ws.onopen = () => { backoff = 800; };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'ai_status' && msg.data?.status) {
            setAiStatus(msg.data.status);
            if (msg.data.status === 'failed') toast.error(L.failed);
            else if (msg.data.status === 'degraded') toast.warning(L.degraded);
            else if (msg.data.status === 'session_ended') toast.info(L.sessionEnded);
          } else if (msg.type === 'call_status' && msg.data?.status === 'subscribed') {
            setAiStatus('subscribed');
          } else if (msg.type === 'coaching_hint' && msg.data) {
            setLastHint(msg.data);
            setHintCount((n) => n + 1);
            setAiStatus('active');
          }
        } catch { /* ignore malformed */ }
      };
      ws.onclose = () => {
        if (!closed) {
          // Backoff and retry — contractor tab kept open.
          setTimeout(connect, backoff);
          backoff = Math.min(backoff * 1.8, 8000);
        }
      };
      ws.onerror = () => {};
    };
    connect();

    return () => {
      closed = true;
      try { wsRef.current?.close(); } catch { /* noop */ }
    };
  }, [callLogId, token, apiBase]);

  const sentimentStyle = useMemo(
    () => SENTIMENT_STYLE[lastHint?.sentiment] || SENTIMENT_STYLE.neutral,
    [lastHint?.sentiment],
  );
  const scoreValue = typeof lastHint?.client_sentiment_score === 'number'
    ? lastHint.client_sentiment_score.toFixed(1)
    : null;

  const statusPill = (() => {
    if (aiStatus === 'active')        return { text: L.live,      cls: 'bg-emerald-100 text-emerald-800 border-emerald-300', pulse: true };
    if (aiStatus === 'degraded')      return { text: 'DEGRADED',  cls: 'bg-amber-100 text-amber-800 border-amber-300',       pulse: false };
    if (aiStatus === 'failed')        return { text: 'FAILED',    cls: 'bg-rose-100 text-rose-800 border-rose-300',          pulse: false };
    if (aiStatus === 'session_ended') return { text: 'ENDED',     cls: 'bg-slate-200 text-slate-700',                        pulse: false };
    if (aiStatus === 'subscribed')    return { text: L.subscribed, cls: 'bg-indigo-100 text-indigo-800 border-indigo-300',   pulse: true };
    return { text: L.offline, cls: 'bg-slate-100 text-slate-600', pulse: false };
  })();

  if (!callLogId) return null;

  return (
    <Card
      className="border-2 border-indigo-200 bg-gradient-to-br from-white to-indigo-50/40"
      data-testid="ai-coach-sidebar"
    >
      <CardContent className="p-0">
        <div className="p-3 sm:p-4 border-b border-indigo-100 flex items-center justify-between gap-2 bg-gradient-to-r from-indigo-600 to-cyan-600 text-white rounded-t-lg">
          <div className="flex items-center gap-2 min-w-0">
            <Bot className="h-5 w-5 flex-shrink-0" />
            <span className="font-bold text-sm sm:text-base truncate">{L.heading}</span>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Badge className={`${statusPill.cls} ${statusPill.pulse ? 'animate-pulse' : ''}`} data-testid="ai-coach-status">
              <Radio className="h-3 w-3 mr-1" />
              {statusPill.text}
            </Badge>
            <Button
              size="sm"
              variant="ghost"
              className="text-white hover:bg-white/20 h-6 w-6 p-0"
              onClick={() => setMinimized((m) => !m)}
              data-testid="ai-coach-minimize-btn"
              title={minimized ? L.expand : L.minimize}
            >
              {minimized ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        {!minimized && (
          <div className="p-3 sm:p-4 space-y-3" data-testid="ai-coach-body">
            {!lastHint && aiStatus !== 'failed' && (
              <div className="text-xs text-slate-500 italic flex items-center gap-2" data-testid="ai-coach-waiting">
                <MessageCircle className="h-3 w-3" />
                {L.waiting}
              </div>
            )}

            {lastHint && (
              <>
                {/* Sentiment row */}
                <div className={`rounded-lg p-3 border ${sentimentStyle.bg} ${sentimentStyle.border}`} data-testid="ai-coach-sentiment">
                  <div className="flex items-center justify-between text-xs">
                    <span className="uppercase tracking-wide text-slate-500 font-semibold">{L.clientSentiment}</span>
                    <div className="flex items-center gap-2">
                      <span className={`inline-block w-2 h-2 rounded-full ${sentimentStyle.dot}`}></span>
                      <span className={`font-bold text-sm ${sentimentStyle.color}`}>
                        {lastHint.sentiment}
                      </span>
                      {scoreValue !== null && (
                        <span className="text-xs text-slate-500 font-mono">({scoreValue})</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Tone alert */}
                {lastHint.tone_alert && (
                  <div className="flex items-center gap-2 text-xs" data-testid="ai-coach-tone-alert">
                    {lastHint.tone_alert === 'about_to_disengage' || lastHint.tone_alert === 'getting_impatient'
                      ? <TrendingDown className="h-4 w-4 text-rose-600" />
                      : <TrendingUp className="h-4 w-4 text-emerald-600" />}
                    <span className="uppercase tracking-wide text-slate-500 font-semibold">{L.tone}:</span>
                    <span className="font-semibold">{TONE_LABEL[lang][lastHint.tone_alert] || lastHint.tone_alert}</span>
                  </div>
                )}

                {/* Coaching hint */}
                {lastHint.coaching_hint && (
                  <div className="rounded-lg p-3 bg-white border border-indigo-200" data-testid="ai-coach-hint">
                    <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-indigo-700 font-bold mb-1">
                      <Sparkles className="h-3 w-3" /> {L.tip}
                    </div>
                    <p className="text-sm text-slate-800 leading-snug">{lastHint.coaching_hint}</p>
                  </div>
                )}

                {/* Suggested next line — distinctive style */}
                {lastHint.suggested_next_line && (
                  <div className="rounded-lg p-3 bg-cyan-50 border-2 border-dashed border-cyan-400" data-testid="ai-coach-suggested-line">
                    <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-cyan-800 font-bold mb-1">
                      <ArrowRight className="h-3 w-3" /> {L.nextLine}
                    </div>
                    <p className="text-sm text-slate-900 leading-snug font-medium italic">
                      &ldquo;{lastHint.suggested_next_line}&rdquo;
                    </p>
                  </div>
                )}

                {/* Compliance flag — prominent amber/red */}
                {lastHint.compliance_flag ? (
                  <div className="rounded-lg p-3 bg-amber-50 border-2 border-amber-400" data-testid="ai-coach-compliance-flag">
                    <div className="flex items-center gap-2 text-amber-900">
                      <AlertTriangle className="h-4 w-4" />
                      <span className="uppercase tracking-wide text-[10px] font-bold">{L.compliance}</span>
                    </div>
                    <p className="text-sm mt-1 font-semibold text-amber-900">
                      {COMPLIANCE_LABEL[lang][lastHint.compliance_flag] || lastHint.compliance_flag}
                    </p>
                  </div>
                ) : (
                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1">
                    <span className="uppercase tracking-wide">{L.compliance}</span>
                    <span>{L.complianceNone}</span>
                  </div>
                )}

                {/* Language pill */}
                <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-100">
                  <span className="uppercase tracking-wide">{L.lang}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {(lastHint.language_detected || 'en').toUpperCase()}
                  </Badge>
                </div>

                <div className="text-[10px] text-slate-300 text-right" data-testid="ai-coach-hint-counter">
                  hint #{hintCount}
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
