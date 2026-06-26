/**
 * iter316 Phase B — Mission B1 + B2
 * Admin Dialer: Browser-based Twilio Voice click-to-call + Call History
 * + AI Insights Expandable Panel.
 *
 * Three-panel layout:
 *   1. LEFT — Dial pad / Outbound form (new call entry)
 *   2. CENTER — Active call modal (when ringing/connected)
 *   3. RIGHT — Call history table with expandable AI Insights row
 *
 * Mission B2 — AI Insights auto-refresh: rows in
 *   ai_processing_status in {"pending","processing"} re-poll every 15s.
 *
 * Graceful degradation:
 *   • If /api/twilio/config returns configured=false → renders a banner
 *     listing the missing env vars and disables the call button.
 *   • If Twilio Voice SDK init fails → falls back to "place via REST"
 *     (server-initiated call from TWILIO_PHONE_NUMBER, no browser audio).
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  PhoneCall, PhoneOff, Mic, MicOff, Loader2, AlertTriangle,
  ChevronDown, ChevronRight, Smile, Meh, Frown, Sparkles,
  Globe, ListChecks, FileText, Volume2, Lock, History,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';

const POLL_INTERVAL_MS = 15000; // Mission B2 — 15s polling for AI status

// ─── Helpers ──────────────────────────────────────────────────────────

const formatDuration = (sec) => {
  if (sec == null || isNaN(sec)) return '—';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
};

const formatDateTime = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

const SENTIMENT_BADGE = {
  positive: { Icon: Smile, cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  neutral:  { Icon: Meh,   cls: 'bg-slate-100 text-slate-700 border-slate-300' },
  negative: { Icon: Frown, cls: 'bg-rose-100 text-rose-800 border-rose-300' },
};

const STATUS_BADGE = {
  initiated:    'bg-slate-100 text-slate-700',
  ringing:      'bg-amber-100 text-amber-800',
  'in-progress':'bg-indigo-100 text-indigo-800',
  answered:     'bg-indigo-100 text-indigo-800',
  completed:    'bg-emerald-100 text-emerald-800',
  busy:         'bg-orange-100 text-orange-800',
  failed:       'bg-rose-100 text-rose-800',
  'no-answer':  'bg-orange-100 text-orange-800',
  canceled:     'bg-slate-100 text-slate-700',
};

const AI_STATUS_BADGE = {
  pending:    { en: 'AI: queued',     fr: 'IA : en file',         cls: 'bg-slate-100 text-slate-700' },
  processing: { en: 'AI: processing', fr: 'IA : en traitement',   cls: 'bg-indigo-100 text-indigo-800' },
  completed:  { en: 'AI: ready',      fr: 'IA : prête',           cls: 'bg-emerald-100 text-emerald-800' },
  failed:     { en: 'AI: failed',     fr: 'IA : échec',           cls: 'bg-rose-100 text-rose-800' },
};

// ─── Main component ──────────────────────────────────────────────────

export default function AdminDialer() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const { user, token } = useAuth();

  const [config, setConfig] = useState(null);
  const [configLoading, setConfigLoading] = useState(true);

  // Outbound form
  const [phone, setPhone] = useState('+1');
  const [clientName, setClientName] = useState('');
  const [clientType, setClientType] = useState('lead');
  const [callPurpose, setCallPurpose] = useState('');
  const [preNotes, setPreNotes] = useState('');

  // Active call state
  const [activeCall, setActiveCall] = useState(null); // {call_log_id, status, started_at}
  const [muted, setMuted] = useState(false);
  const [twilioDevice, setTwilioDevice] = useState(null);
  const [twilioConnection, setTwilioConnection] = useState(null);
  const [deviceReady, setDeviceReady] = useState(false);

  // History
  const [calls, setCalls] = useState([]);
  const [callsLoading, setCallsLoading] = useState(false);
  const [expandedRowId, setExpandedRowId] = useState(null);
  const [expandedDetail, setExpandedDetail] = useState(null);

  const isAdmin = user && (user.role === 'admin' || user.role === 'super_admin');
  const isContractor = user && user.role === 'dialer_contractor';

  // ─── Config probe ─────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    async function probe() {
      setConfigLoading(true);
      try {
        const r = await axios.get(`${API_BASE}/twilio/config`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setConfig(r.data);
      } catch (e) {
        if (!cancelled) setConfig({ configured: false, missing: ['unable to reach /api/twilio/config'], error: e?.message });
      } finally {
        if (!cancelled) setConfigLoading(false);
      }
    }
    if (token) probe();
    return () => { cancelled = true; };
  }, [token]);

  // ─── Twilio Voice SDK init ─────────────────────────────────────────
  const initTwilioDevice = useCallback(async () => {
    if (!config?.can_mint_tokens) return;
    try {
      const r = await axios.post(`${API_BASE}/twilio/token`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const sdk = await import('@twilio/voice-sdk');
      const dev = new sdk.Device(r.data.token, {
        codecPreferences: ['opus', 'pcmu'],
        logLevel: 'warn',
      });
      dev.on('registered', () => setDeviceReady(true));
      dev.on('error', (err) => {
        console.error('[Twilio] device error:', err);
        toast.error(fr ? `Erreur Twilio : ${err.message}` : `Twilio error: ${err.message}`);
      });
      dev.on('disconnect', () => {
        setTwilioConnection(null);
        setActiveCall(null);
      });
      await dev.register();
      setTwilioDevice(dev);
    } catch (e) {
      console.warn('[Twilio] SDK init failed — falling back to REST place_call:', e?.message);
      setDeviceReady(false);
    }
  }, [config, token, fr]);

  useEffect(() => {
    if (config?.can_mint_tokens && !twilioDevice) initTwilioDevice();
  }, [config?.can_mint_tokens, initTwilioDevice, twilioDevice]);

  // ─── Calls history fetch + 15s AI status poll (Mission B2) ─────────
  const fetchCalls = useCallback(async () => {
    if (!token) return;
    try {
      const r = await axios.get(`${API_BASE}/twilio/calls?limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCalls(r.data.items || []);
    } catch {
      // best-effort
    } finally {
      setCallsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    setCallsLoading(true);
    fetchCalls();
  }, [fetchCalls]);

  // Auto-poll while any row is pending/processing.
  useEffect(() => {
    const hasInFlightAi = calls.some(
      (c) => ['pending', 'processing'].includes(c.ai_processing_status),
    );
    if (!hasInFlightAi) return undefined;
    const t = setInterval(fetchCalls, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [calls, fetchCalls]);

  // ─── Place outbound call ──────────────────────────────────────────
  const startCall = async () => {
    if (!config?.can_place_calls) {
      toast.error(fr ? 'Twilio non configuré sur le serveur.' : 'Twilio not configured on the server.');
      return;
    }
    if (!phone.startsWith('+') || phone.length < 8) {
      toast.error(fr ? 'Le numéro doit être au format E.164 (+14155550123).' : 'Phone must be E.164 format (+14155550123).');
      return;
    }
    try {
      const r = await axios.post(`${API_BASE}/twilio/call`, {
        client_phone: phone.trim(),
        client_name: clientName,
        client_type: clientType,
        call_purpose: callPurpose,
        pre_call_notes: preNotes,
      }, { headers: { Authorization: `Bearer ${token}` } });

      const callLogId = r.data.call_log_id;
      setActiveCall({ call_log_id: callLogId, status: 'initiated', started_at: new Date().toISOString() });

      // If the browser SDK is ready, dial OUT through the browser so audio
      // streams locally (caller_id = TWILIO_PHONE_NUMBER, set in the TwiML
      // app's Voice Request URL). Otherwise fall back to REST.
      if (twilioDevice && deviceReady) {
        try {
          const conn = await twilioDevice.connect({ params: { To: phone.trim() } });
          setTwilioConnection(conn);
          conn.on('accept', () => setActiveCall((p) => p && { ...p, status: 'answered' }));
          conn.on('disconnect', () => {
            setTwilioConnection(null);
            setActiveCall(null);
            fetchCalls();
          });
          conn.on('error', (err) => {
            toast.error(fr ? `Appel échoué : ${err.message}` : `Call failed: ${err.message}`);
            setActiveCall(null);
          });
        } catch (e) {
          toast.error(fr ? "Échec de l'établissement de l'appel" : 'Failed to establish call');
          setActiveCall(null);
        }
      } else {
        toast.info(fr
          ? 'Mode REST : appel placé via Twilio sans audio dans le navigateur.'
          : 'REST mode: call placed via Twilio without in-browser audio.');
      }

      fetchCalls();
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = (typeof d === 'object' ? (fr ? d?.message_fr : d?.message_en) : d) || e?.message;
      toast.error(msg || (fr ? "Échec de l'appel" : 'Call failed'));
    }
  };

  const hangup = () => {
    if (twilioConnection) {
      try { twilioConnection.disconnect(); } catch { /* noop */ }
    }
    setActiveCall(null);
    setTwilioConnection(null);
    fetchCalls();
  };

  const toggleMute = () => {
    if (!twilioConnection) return;
    const next = !muted;
    try { twilioConnection.mute(next); } catch { /* noop */ }
    setMuted(next);
  };

  // ─── Expand row & fetch AI insights ───────────────────────────────
  const toggleExpand = async (callId) => {
    if (expandedRowId === callId) {
      setExpandedRowId(null);
      setExpandedDetail(null);
      return;
    }
    setExpandedRowId(callId);
    setExpandedDetail(null);
    try {
      const r = await axios.get(`${API_BASE}/twilio/calls/${callId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setExpandedDetail(r.data);
    } catch (e) {
      toast.error(fr ? "Impossible de charger les détails de l'appel" : 'Could not load call details');
      setExpandedRowId(null);
    }
  };

  // ─── Render ───────────────────────────────────────────────────────
  if (configLoading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="dialer-loading">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-3" />
        <span>{fr ? 'Chargement du composeur…' : 'Loading dialer…'}</span>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-7xl py-4 px-3" data-testid="admin-dialer-page">
      <header className="mb-4">
        <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="dialer-title">
          <PhoneCall className="h-7 w-7" />
          {fr ? 'Composeur BidVex' : 'BidVex Dialer'}
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {fr
            ? 'Cliquez pour appeler vos clients, prenez des notes et profitez des analyses IA après chaque appel.'
            : 'Click to call clients, capture notes, and review AI insights after every call.'}
        </p>
      </header>

      {/* Config banner */}
      {!config?.configured && (
        <Card className="mb-4 border-2 border-amber-300 bg-amber-50" data-testid="dialer-config-banner">
          <CardContent className="p-3 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold text-amber-900">
                {fr ? 'Twilio n\u2019est pas entièrement configuré' : 'Twilio not fully configured'}
              </p>
              <p className="text-amber-800">
                {fr
                  ? 'Le composeur sera disponible une fois que l\u2019administrateur aura configuré les variables suivantes :'
                  : 'The dialer will be available once an administrator sets the following environment variables:'}{' '}
                <span className="font-mono text-xs bg-white px-2 py-0.5 rounded border border-amber-200">
                  {(config?.missing || []).join(', ') || '—'}
                </span>
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* THREE-PANEL LAYOUT */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* LEFT — Outbound form / dial pad */}
        <Card className="lg:col-span-4" data-testid="dialer-outbound-panel">
          <CardContent className="p-4 space-y-3">
            <h2 className="font-semibold text-lg flex items-center gap-2">
              <PhoneCall className="h-5 w-5" />
              {fr ? 'Nouvel appel' : 'New call'}
            </h2>
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-600">
                {fr ? 'Numéro (E.164)' : 'Phone (E.164)'}
              </label>
              <Input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+14155550123"
                data-testid="dialer-phone-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-600">
                {fr ? 'Nom du client' : 'Client name'}
              </label>
              <Input
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder={fr ? 'ex. Jean Tremblay' : 'e.g. John Smith'}
                data-testid="dialer-client-name-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-600">{fr ? 'Type' : 'Type'}</label>
                <select
                  value={clientType}
                  onChange={(e) => setClientType(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm"
                  data-testid="dialer-client-type-select"
                >
                  <option value="lead">{fr ? 'Prospect' : 'Lead'}</option>
                  <option value="partner">{fr ? 'Partenaire' : 'Partner'}</option>
                  <option value="buyer">{fr ? 'Acheteur' : 'Buyer'}</option>
                  <option value="seller">{fr ? 'Vendeur' : 'Seller'}</option>
                  <option value="dealer">{fr ? 'Concessionnaire' : 'Dealer'}</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-600">{fr ? 'Objet' : 'Purpose'}</label>
                <Input
                  value={callPurpose}
                  onChange={(e) => setCallPurpose(e.target.value)}
                  placeholder={fr ? 'Ex. Recouvrement' : 'e.g. Onboarding'}
                  data-testid="dialer-call-purpose-input"
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-600">{fr ? 'Notes pré-appel' : 'Pre-call notes'}</label>
              <Textarea
                value={preNotes}
                onChange={(e) => setPreNotes(e.target.value)}
                rows={3}
                placeholder={fr ? 'Ce que vous voulez aborder…' : 'What you want to cover…'}
                data-testid="dialer-pre-notes-input"
              />
            </div>
            <Button
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={startCall}
              disabled={!config?.can_place_calls || !!activeCall}
              data-testid="dialer-call-btn"
            >
              <PhoneCall className="h-4 w-4 mr-2" />
              {fr ? 'Appeler maintenant' : 'Call now'}
            </Button>
            {config?.twilio_phone_number && (
              <p className="text-[11px] text-slate-500" data-testid="dialer-caller-id">
                {fr ? 'Numéro affiché : ' : 'Caller ID: '}
                <span className="font-mono">{config.twilio_phone_number}</span>
              </p>
            )}
          </CardContent>
        </Card>

        {/* CENTER — Active call modal placeholder */}
        <Card className="lg:col-span-3" data-testid="dialer-active-panel">
          <CardContent className="p-4">
            <h2 className="font-semibold text-lg flex items-center gap-2 mb-3">
              <Volume2 className="h-5 w-5" />
              {fr ? 'Appel en cours' : 'Active call'}
            </h2>
            {!activeCall ? (
              <div className="text-sm text-slate-500 py-6 text-center" data-testid="dialer-no-active-call">
                {fr ? 'Aucun appel en cours.' : 'No call in progress.'}
              </div>
            ) : (
              <div className="space-y-3" data-testid="dialer-active-call-card">
                <div className="text-center py-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">
                    {fr ? 'En communication avec' : 'On call with'}
                  </p>
                  <p className="text-lg font-semibold mt-1">{clientName || phone}</p>
                  <p className="text-xs text-slate-500 font-mono mt-1">{phone}</p>
                  <Badge className={`${STATUS_BADGE[activeCall.status] || 'bg-slate-100'} mt-2`}>
                    {activeCall.status}
                  </Badge>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <Button
                    variant="outline"
                    onClick={toggleMute}
                    disabled={!twilioConnection}
                    data-testid="dialer-mute-btn"
                  >
                    {muted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={hangup}
                    data-testid="dialer-hangup-btn"
                  >
                    <PhoneOff className="h-4 w-4 mr-2" />
                    {fr ? 'Raccrocher' : 'Hang up'}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* RIGHT — Call history */}
        <Card className="lg:col-span-5" data-testid="dialer-history-panel">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-lg flex items-center gap-2">
                <History className="h-5 w-5" />
                {fr ? 'Historique des appels' : 'Call history'}
              </h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchCalls}
                data-testid="dialer-history-refresh-btn"
              >
                {fr ? 'Actualiser' : 'Refresh'}
              </Button>
            </div>
            {callsLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-500" data-testid="dialer-history-loading">
                <Loader2 className="h-4 w-4 animate-spin" />
                {fr ? 'Chargement…' : 'Loading…'}
              </div>
            ) : calls.length === 0 ? (
              <div className="text-sm text-slate-500 py-6 text-center" data-testid="dialer-history-empty">
                {fr ? 'Aucun appel enregistré pour l\u2019instant.' : 'No calls logged yet.'}
              </div>
            ) : (
              <ul className="divide-y" data-testid="dialer-history-list">
                {calls.map((c) => (
                  <CallHistoryRow
                    key={c._id || c.id}
                    call={c}
                    isAdmin={isAdmin}
                    fr={fr}
                    token={token}
                    expanded={expandedRowId === (c._id || c.id)}
                    detail={expandedRowId === (c._id || c.id) ? expandedDetail : null}
                    onToggle={() => toggleExpand(c._id || c.id)}
                  />
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Sub-component: Call history row + AI Insights ───────────────────

function CallHistoryRow({ call, expanded, detail, onToggle, isAdmin, fr, token }) {
  const callId = call._id || call.id;
  const aiStatus = call.ai_processing_status || 'pending';
  const aiCfg = AI_STATUS_BADGE[aiStatus] || AI_STATUS_BADGE.pending;
  const sentiment = detail?.sentiment_label || call.sentiment_label;
  const SentimentIcon = sentiment ? (SENTIMENT_BADGE[sentiment]?.Icon || Meh) : Meh;
  const sentimentCls = sentiment ? (SENTIMENT_BADGE[sentiment]?.cls || '') : '';

  const playRecording = async () => {
    if (!isAdmin) return; // raw audio admin-only
    try {
      const r = await axios.get(`${API_BASE}/twilio/calls/${callId}/recording`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob',
      });
      const url = URL.createObjectURL(r.data);
      const audio = new Audio(url);
      audio.play();
    } catch {
      toast.error(fr ? 'Lecture impossible.' : 'Playback failed.');
    }
  };

  return (
    <li className="py-2" data-testid={`dialer-history-row-${callId}`}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between text-left hover:bg-slate-50 px-2 py-2 rounded"
        data-testid={`dialer-history-toggle-${callId}`}
      >
        <div className="flex items-center gap-2 min-w-0">
          {expanded ? <ChevronDown className="h-4 w-4 flex-shrink-0" /> : <ChevronRight className="h-4 w-4 flex-shrink-0" />}
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{call.client_name || call.client_phone}</p>
            <p className="text-xs text-slate-500 font-mono truncate">{call.client_phone}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge className={STATUS_BADGE[call.status] || 'bg-slate-100'}>{call.status}</Badge>
          <Badge className={aiCfg.cls} data-testid={`dialer-ai-status-${callId}`}>
            <Sparkles className="h-3 w-3 mr-1" />
            {fr ? aiCfg.fr : aiCfg.en}
          </Badge>
          {sentiment && (
            <Badge className={sentimentCls} data-testid={`dialer-sentiment-${callId}`}>
              <SentimentIcon className="h-3 w-3 mr-1" />
              {sentiment}
            </Badge>
          )}
          <span className="text-xs text-slate-500 hidden sm:inline">
            {formatDuration(call.duration_seconds)}
          </span>
        </div>
      </button>

      {expanded && (
        <div
          className="ml-6 mt-2 p-3 bg-slate-50 dark:bg-slate-900/30 rounded border border-slate-200"
          data-testid={`dialer-ai-insights-${callId}`}
        >
          {!detail ? (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              {fr ? 'Chargement…' : 'Loading…'}
            </div>
          ) : (
            <AIInsightsPanel call={detail} isAdmin={isAdmin} fr={fr} onPlayRecording={playRecording} />
          )}
          <p className="text-[11px] text-slate-400 mt-2">
            {fr ? 'Démarré le ' : 'Started at '}{formatDateTime(call.initiated_at)}
          </p>
        </div>
      )}
    </li>
  );
}

function AIInsightsPanel({ call, isAdmin, fr, onPlayRecording }) {
  const [lang, setLang] = useState(fr ? 'fr' : 'en');
  const status = call.ai_processing_status || 'pending';

  const speakers = call.transcript_speakers || [];
  const transcript = lang === 'fr' ? call.transcript_fr : call.transcript_en;
  const actionItems = call.action_items || [];

  return (
    <div className="space-y-3" data-testid="ai-insights-panel">
      {/* Status / pending / failed states */}
      {status !== 'completed' && (
        <div className="text-xs flex items-center gap-2" data-testid="ai-insights-status-line">
          {status === 'failed' ? (
            <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />
          ) : (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600" />
          )}
          <span>
            {status === 'failed' && (fr
              ? 'Échec de l\u2019analyse IA. Réessai automatique : non. L\u2019enregistrement reste disponible.'
              : 'AI analysis failed. No further auto-retry. The recording remains available.')}
            {status === 'processing' && (fr ? 'Analyse IA en cours…' : 'AI analysis in progress…')}
            {status === 'pending' && (fr ? 'Analyse IA en file d\u2019attente…' : 'AI analysis queued…')}
          </span>
        </div>
      )}

      {/* Summary */}
      {call.call_summary && (
        <div data-testid="ai-insights-summary">
          <p className="text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
            <FileText className="h-3.5 w-3.5" />
            {fr ? 'Résumé' : 'Summary'}
          </p>
          <p className="text-sm text-slate-700">{call.call_summary}</p>
        </div>
      )}

      {/* Action items */}
      {actionItems.length > 0 && (
        <div data-testid="ai-insights-actions">
          <p className="text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
            <ListChecks className="h-3.5 w-3.5" />
            {fr ? 'Actions à suivre' : 'Action items'}
          </p>
          <ul className="space-y-1">
            {actionItems.map((a, idx) => (
              <li key={idx} className="text-sm flex items-start gap-2">
                <input type="checkbox" className="mt-1 flex-shrink-0" data-testid={`ai-action-item-${idx}`} />
                <span>{a}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Bilingual transcript */}
      {(call.transcript_en || call.transcript_fr) && (
        <div data-testid="ai-insights-transcript">
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-semibold text-slate-700 flex items-center gap-1">
              <Globe className="h-3.5 w-3.5" />
              {fr ? 'Transcription' : 'Transcript'}
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setLang('en')}
                className={`text-xs px-2 py-0.5 rounded ${lang === 'en' ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`}
                data-testid="transcript-lang-en"
              >
                EN
              </button>
              <button
                onClick={() => setLang('fr')}
                className={`text-xs px-2 py-0.5 rounded ${lang === 'fr' ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`}
                data-testid="transcript-lang-fr"
              >
                FR
              </button>
            </div>
          </div>
          {speakers.length > 0 ? (
            <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1" data-testid="ai-insights-diarized">
              {speakers.map((s, idx) => (
                <div key={idx} className="text-sm">
                  <span className={`font-semibold text-xs ${s.speaker === 'Agent' ? 'text-indigo-700' : 'text-emerald-700'}`}>
                    {s.speaker}:
                  </span>{' '}
                  <span>{s.text}</span>
                </div>
              ))}
            </div>
          ) : transcript ? (
            <pre className="text-sm whitespace-pre-wrap max-h-72 overflow-y-auto pr-1">{transcript}</pre>
          ) : (
            <p className="text-xs text-slate-500">{fr ? 'Transcription indisponible.' : 'Transcript not available.'}</p>
          )}
        </div>
      )}

      {/* Admin-only raw audio playback */}
      {isAdmin && call.recording_url ? (
        <Button
          size="sm"
          variant="outline"
          onClick={onPlayRecording}
          data-testid="dialer-play-recording-btn"
        >
          <Volume2 className="h-4 w-4 mr-1" />
          {fr ? 'Écouter l\u2019enregistrement (admin)' : 'Play recording (admin)'}
        </Button>
      ) : call.recording_url && !isAdmin ? (
        <p className="text-[11px] text-slate-500 flex items-center gap-1" data-testid="dialer-recording-locked">
          <Lock className="h-3 w-3" />
          {fr ? 'L\u2019accès à l\u2019enregistrement audio est réservé aux administrateurs.' : 'Raw audio access is admin-only.'}
        </p>
      ) : null}
    </div>
  );
}
