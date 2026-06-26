/**
 * iter316-C — Admin "Contractor Drill-in" page.
 * Route: /admin/contractors/:contractorId
 *
 * 4 tabs:
 *   • Calls      — list + AI insights expansion + admin-only audio playback
 *   • AI Report  — aggregate sentiment + top action items + completion rates
 *   • Clients    — referred clients with listing counts
 *   • Dashboard  — mirror of the contractor's own dashboard (earnings/Stripe)
 *
 * Backed by GET /api/twilio/admin/contractors/{id}/profile.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  ArrowLeft, ShieldCheck, PhoneCall, Sparkles, Users, Wallet,
  CheckCircle2, AlertTriangle, Smile, Meh, Frown, Volume2, Loader2,
  ChevronDown, ChevronRight, FileText, ListChecks, Globe, Lock,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';

function money(amount) {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' })
    .format(Number(amount || 0));
}

function formatDuration(sec) {
  if (sec == null || Number.isNaN(sec)) return '—';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

const SENT_ICON = { positive: Smile, neutral: Meh, negative: Frown };
const SENT_CLS = {
  positive: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  neutral:  'bg-slate-100 text-slate-700 border-slate-300',
  negative: 'bg-rose-100 text-rose-800 border-rose-300',
};
const AI_STATUS_CLS = {
  completed:  'bg-emerald-100 text-emerald-800',
  failed:     'bg-rose-100 text-rose-800',
  processing: 'bg-indigo-100 text-indigo-800',
  pending:    'bg-slate-100 text-slate-700',
};

// ─── Page ─────────────────────────────────────────────────────────────

export default function AdminContractorProfilePage() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const { contractorId } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!token || !contractorId) return;
    setLoading(true);
    try {
      const r = await axios.get(
        `${API_BASE}/twilio/admin/contractors/${contractorId}/profile`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setData(r.data);
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message);
    } finally {
      setLoading(false);
    }
  }, [contractorId, token]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="contractor-profile-loading">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-2" />
        <span>{fr ? 'Chargement…' : 'Loading…'}</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container mx-auto max-w-3xl py-12 px-4">
        <Card className="border-2 border-rose-300 bg-rose-50" data-testid="contractor-profile-error">
          <CardContent className="p-6">
            <p className="text-sm">{fr ? 'Erreur de chargement.' : 'Failed to load profile.'} {String(error || '')}</p>
            <Button variant="outline" onClick={() => navigate(-1)} className="mt-3">
              <ArrowLeft className="h-4 w-4 mr-1" />
              {fr ? 'Retour' : 'Back'}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const c = data.contractor;
  const stripe = data.stripe || {};
  const earnings = data.earnings || {};
  const ai = data.ai_summary || {};

  return (
    <div className="container mx-auto max-w-7xl py-4 px-3 space-y-4" data-testid="contractor-profile-page">
      {/* Header */}
      <header className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/admin?tab=dialer')} data-testid="contractor-profile-back-btn">
            <ArrowLeft className="h-4 w-4 mr-1" /> {fr ? 'Retour' : 'Back to contractors'}
          </Button>
          <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2 mt-1" data-testid="contractor-profile-title">
            <ShieldCheck className="h-7 w-7 text-indigo-600" />
            {c.name || c.email}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            <span className="font-mono">{c.email}</span>
            {c.phone ? <> · {c.phone}</> : null}
            {c.province ? <> · {c.province}</> : null}
            {c.affiliate_code ? <> · {fr ? 'Code parrainage : ' : 'Referral code: '}<span className="font-mono">{c.affiliate_code}</span></> : null}
          </p>
          {c.role_warning && (
            <Badge className="bg-amber-100 text-amber-800 mt-2" data-testid="contractor-profile-demoted-warning">
              <AlertTriangle className="h-3 w-3 mr-1" />
              {fr ? 'Cet utilisateur n\u2019est plus un contractant (historique préservé).' : 'No longer a contractor — history is preserved for audit.'}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={load} data-testid="contractor-profile-refresh-btn">
            {fr ? 'Actualiser' : 'Refresh'}
          </Button>
        </div>
      </header>

      {/* Snapshot cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="contractor-profile-snapshot">
        <Card data-testid="snap-accrued">
          <CardContent className="p-3">
            <p className="text-[11px] uppercase text-slate-500">{fr ? 'Accumulé' : 'Accrued'}</p>
            <p className="text-xl font-bold">{money(earnings.lifetime_accrued)}</p>
          </CardContent>
        </Card>
        <Card data-testid="snap-paid">
          <CardContent className="p-3">
            <p className="text-[11px] uppercase text-slate-500">{fr ? 'Versé' : 'Paid'}</p>
            <p className="text-xl font-bold">{money(earnings.lifetime_paid)}</p>
          </CardContent>
        </Card>
        <Card data-testid="snap-calls">
          <CardContent className="p-3">
            <p className="text-[11px] uppercase text-slate-500">{fr ? 'Appels' : 'Calls'}</p>
            <p className="text-xl font-bold">{data.calls_total || 0}</p>
          </CardContent>
        </Card>
        <Card data-testid="snap-referrals">
          <CardContent className="p-3">
            <p className="text-[11px] uppercase text-slate-500">{fr ? 'Clients référés' : 'Referred'}</p>
            <p className="text-xl font-bold">{data.referred_count || 0}</p>
          </CardContent>
        </Card>
      </div>

      {/* Stripe payout status */}
      <Card className={stripe.connected ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'} data-testid="contractor-profile-stripe">
        <CardContent className="p-3 flex items-center gap-2">
          {stripe.connected
            ? <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            : <AlertTriangle className="h-5 w-5 text-amber-600" />}
          <div className="text-sm">
            <p className="font-semibold">
              {stripe.connected
                ? (fr ? 'Versements Stripe actifs' : 'Stripe payouts active')
                : (fr ? 'Stripe non connecté' : 'Stripe not connected')}
            </p>
            <p className="text-xs text-slate-600">
              {stripe.account_id
                ? <>{fr ? 'Compte : ' : 'Account: '}<span className="font-mono">{stripe.account_id}</span></>
                : (fr ? 'Aucun compte Stripe Connect lié.' : 'No Stripe Connect account linked.')}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="calls" data-testid="contractor-profile-tabs">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="calls" data-testid="tab-calls">
            <PhoneCall className="h-4 w-4 mr-1" />
            {fr ? 'Appels' : 'Calls'} ({(data.recent_calls || []).length})
          </TabsTrigger>
          <TabsTrigger value="ai" data-testid="tab-ai">
            <Sparkles className="h-4 w-4 mr-1" />
            {fr ? 'Rapport IA' : 'AI Report'}
          </TabsTrigger>
          <TabsTrigger value="clients" data-testid="tab-clients">
            <Users className="h-4 w-4 mr-1" />
            {fr ? 'Clients référés' : 'Referred Clients'} ({data.referred_count || 0})
          </TabsTrigger>
          <TabsTrigger value="dashboard" data-testid="tab-dashboard">
            <Wallet className="h-4 w-4 mr-1" />
            {fr ? 'Tableau de bord' : 'Dashboard'}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="calls" className="mt-3">
          <CallsTab calls={data.recent_calls || []} token={token} fr={fr} />
        </TabsContent>

        <TabsContent value="ai" className="mt-3">
          <AiReportTab ai={ai} fr={fr} />
        </TabsContent>

        <TabsContent value="clients" className="mt-3">
          <ClientsTab clients={data.referred_accounts || []} fr={fr} />
        </TabsContent>

        <TabsContent value="dashboard" className="mt-3">
          <DashboardTab data={data} fr={fr} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ─── Calls Tab ────────────────────────────────────────────────────────

function CallsTab({ calls, token, fr }) {
  const [expanded, setExpanded] = useState(null);
  const [detail, setDetail] = useState(null);

  const onToggle = async (id) => {
    if (expanded === id) { setExpanded(null); setDetail(null); return; }
    setExpanded(id);
    setDetail(null);
    try {
      const r = await axios.get(`${API_BASE}/twilio/calls/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDetail(r.data);
    } catch {
      toast.error(fr ? 'Impossible de charger les détails.' : 'Could not load call details.');
      setExpanded(null);
    }
  };

  if (calls.length === 0) {
    return (
      <Card><CardContent className="p-6 text-sm text-slate-500 text-center" data-testid="calls-empty">
        {fr ? 'Aucun appel encore.' : 'No calls yet.'}
      </CardContent></Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <ul className="divide-y" data-testid="calls-list">
          {calls.map((c) => {
            const cid = c._id || c.id;
            const isOpen = expanded === cid;
            const SentIcon = c.sentiment_label ? (SENT_ICON[c.sentiment_label] || Meh) : null;
            const aiCls = AI_STATUS_CLS[c.ai_processing_status] || AI_STATUS_CLS.pending;
            return (
              <li key={cid} data-testid={`call-row-${cid}`}>
                <button
                  type="button"
                  onClick={() => onToggle(cid)}
                  className="w-full flex items-center justify-between hover:bg-slate-50 px-3 py-2 text-left"
                  data-testid={`call-toggle-${cid}`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{c.client_name || c.client_phone}</p>
                      <p className="text-xs text-slate-500 font-mono truncate">{c.client_phone}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Badge className={aiCls}>{c.ai_processing_status || 'pending'}</Badge>
                    {SentIcon && (
                      <Badge className={SENT_CLS[c.sentiment_label]} data-testid={`call-sentiment-${cid}`}>
                        <SentIcon className="h-3 w-3 mr-1" />{c.sentiment_label}
                      </Badge>
                    )}
                    <span className="text-xs text-slate-500 hidden sm:inline">{formatDuration(c.duration_seconds)}</span>
                  </div>
                </button>
                {isOpen && (
                  <div className="px-4 pb-3 bg-slate-50 border-t" data-testid={`call-detail-${cid}`}>
                    {!detail ? (
                      <div className="text-xs text-slate-500 py-2">
                        <Loader2 className="inline h-3 w-3 animate-spin mr-1" />
                        {fr ? 'Chargement…' : 'Loading…'}
                      </div>
                    ) : (
                      <CallDetail call={detail} token={token} fr={fr} />
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}

function CallDetail({ call, token, fr }) {
  const [lang, setLang] = useState(fr ? 'fr' : 'en');
  const transcript = lang === 'fr' ? call.transcript_fr : call.transcript_en;
  const speakers = call.transcript_speakers || [];

  const playRecording = async () => {
    try {
      const r = await axios.get(`${API_BASE}/twilio/calls/${call._id || call.id}/recording`, {
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
    <div className="space-y-3 pt-2 text-sm">
      {/* Contractor's typed notes — admin oversight */}
      {(call.pre_call_notes || call.post_call_notes) && (
        <div data-testid="call-detail-notes">
          <p className="text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
            <FileText className="h-3.5 w-3.5" />
            {fr ? 'Notes du contractant' : 'Contractor notes'}
          </p>
          {call.pre_call_notes && <p><span className="text-xs text-slate-500">{fr ? 'Pré-appel : ' : 'Pre-call: '}</span>{call.pre_call_notes}</p>}
          {call.post_call_notes && <p className="mt-1"><span className="text-xs text-slate-500">{fr ? 'Post-appel : ' : 'Post-call: '}</span>{call.post_call_notes}</p>}
          {call.outcome && <p className="text-xs text-slate-500 mt-1">{fr ? 'Résultat : ' : 'Outcome: '}<Badge variant="outline">{call.outcome}</Badge></p>}
        </div>
      )}

      {call.call_summary && (
        <div data-testid="call-detail-summary">
          <p className="text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
            <Sparkles className="h-3.5 w-3.5" />
            {fr ? 'Résumé IA' : 'AI Summary'}
          </p>
          <p>{call.call_summary}</p>
        </div>
      )}

      {(call.action_items || []).length > 0 && (
        <div data-testid="call-detail-actions">
          <p className="text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
            <ListChecks className="h-3.5 w-3.5" />
            {fr ? 'Actions' : 'Action items'}
          </p>
          <ul className="list-disc list-inside space-y-0.5">
            {call.action_items.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      {(transcript || speakers.length > 0) && (
        <div data-testid="call-detail-transcript">
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-semibold text-slate-700 flex items-center gap-1">
              <Globe className="h-3.5 w-3.5" />
              {fr ? 'Transcription' : 'Transcript'}
            </p>
            <div className="flex gap-1">
              <button onClick={() => setLang('en')} className={`text-xs px-2 py-0.5 rounded ${lang === 'en' ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`} data-testid="call-transcript-en">EN</button>
              <button onClick={() => setLang('fr')} className={`text-xs px-2 py-0.5 rounded ${lang === 'fr' ? 'bg-indigo-600 text-white' : 'bg-slate-200'}`} data-testid="call-transcript-fr">FR</button>
            </div>
          </div>
          {speakers.length > 0 ? (
            <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
              {speakers.map((s, i) => (
                <div key={i} className="text-sm">
                  <span className={`font-semibold text-xs ${s.speaker === 'Agent' ? 'text-indigo-700' : 'text-emerald-700'}`}>{s.speaker}:</span>{' '}
                  <span>{s.text}</span>
                </div>
              ))}
            </div>
          ) : (
            <pre className="text-sm whitespace-pre-wrap max-h-64 overflow-y-auto pr-1">{transcript}</pre>
          )}
        </div>
      )}

      {call.recording_url && (
        <Button size="sm" variant="outline" onClick={playRecording} data-testid="call-play-recording-btn">
          <Volume2 className="h-4 w-4 mr-1" />
          {fr ? 'Écouter (admin)' : 'Play recording (admin)'}
        </Button>
      )}
      {!call.recording_url && (
        <p className="text-[11px] text-slate-500 flex items-center gap-1">
          <Lock className="h-3 w-3" />
          {fr ? 'Aucun enregistrement disponible.' : 'No recording available.'}
        </p>
      )}
    </div>
  );
}

// ─── AI Report Tab ────────────────────────────────────────────────────

function AiReportTab({ ai, fr }) {
  const total = (ai.sentiment?.positive || 0) + (ai.sentiment?.neutral || 0) + (ai.sentiment?.negative || 0);
  const pct = (n) => total === 0 ? '0%' : `${Math.round((n / total) * 100)}%`;

  return (
    <div className="space-y-3" data-testid="ai-report-tab">
      <Card>
        <CardContent className="p-4">
          <h3 className="font-semibold mb-3">{fr ? 'Statut du pipeline IA' : 'AI pipeline status'}</h3>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div className="rounded border p-2"><span className="text-xs text-slate-500 block">{fr ? 'Complétés' : 'Completed'}</span><span className="text-lg font-bold text-emerald-600">{ai.completed || 0}</span></div>
            <div className="rounded border p-2"><span className="text-xs text-slate-500 block">{fr ? 'En attente' : 'Pending'}</span><span className="text-lg font-bold text-indigo-600">{ai.pending || 0}</span></div>
            <div className="rounded border p-2"><span className="text-xs text-slate-500 block">{fr ? 'Échoués' : 'Failed'}</span><span className="text-lg font-bold text-rose-600">{ai.failed || 0}</span></div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <h3 className="font-semibold mb-3">{fr ? 'Sentiment global' : 'Overall sentiment'}</h3>
          <div className="grid grid-cols-3 gap-2 text-sm" data-testid="sentiment-breakdown">
            <div className="rounded border p-2 bg-emerald-50">
              <Smile className="h-4 w-4 text-emerald-600 mb-1" />
              <p className="text-xs text-slate-600">{fr ? 'Positifs' : 'Positive'}</p>
              <p className="text-lg font-bold">{ai.sentiment?.positive || 0}</p>
              <p className="text-[11px] text-slate-500">{pct(ai.sentiment?.positive || 0)}</p>
            </div>
            <div className="rounded border p-2 bg-slate-50">
              <Meh className="h-4 w-4 text-slate-500 mb-1" />
              <p className="text-xs text-slate-600">{fr ? 'Neutres' : 'Neutral'}</p>
              <p className="text-lg font-bold">{ai.sentiment?.neutral || 0}</p>
              <p className="text-[11px] text-slate-500">{pct(ai.sentiment?.neutral || 0)}</p>
            </div>
            <div className="rounded border p-2 bg-rose-50">
              <Frown className="h-4 w-4 text-rose-600 mb-1" />
              <p className="text-xs text-slate-600">{fr ? 'Négatifs' : 'Negative'}</p>
              <p className="text-lg font-bold">{ai.sentiment?.negative || 0}</p>
              <p className="text-[11px] text-slate-500">{pct(ai.sentiment?.negative || 0)}</p>
            </div>
          </div>
          {ai.avg_sentiment_score !== null && ai.avg_sentiment_score !== undefined && (
            <p className="text-xs text-slate-600 mt-3">
              {fr ? 'Score moyen : ' : 'Average score: '}
              <span className="font-mono font-bold">{Number(ai.avg_sentiment_score).toFixed(2)}</span>
              <span className="text-slate-500"> ({fr ? 'plage [-1, +1]' : 'range [-1, +1]'})</span>
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <h3 className="font-semibold mb-3">{fr ? 'Actions les plus fréquentes' : 'Most frequent action items'}</h3>
          {(ai.top_action_items || []).length === 0 ? (
            <p className="text-sm text-slate-500" data-testid="top-actions-empty">
              {fr ? 'Aucune action extraite encore.' : 'No action items extracted yet.'}
            </p>
          ) : (
            <ul className="space-y-1 text-sm" data-testid="top-actions-list">
              {ai.top_action_items.map((a, i) => (
                <li key={i} className="flex items-center justify-between gap-2">
                  <span>{a.text}</span>
                  <Badge variant="outline">×{a.count}</Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Clients Tab ──────────────────────────────────────────────────────

function ClientsTab({ clients, fr }) {
  if (clients.length === 0) {
    return (
      <Card><CardContent className="p-6 text-sm text-slate-500 text-center" data-testid="clients-empty">
        {fr ? 'Aucun client référé.' : 'No referred clients yet.'}
      </CardContent></Card>
    );
  }
  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="clients-table">
            <thead>
              <tr className="text-xs text-slate-500 border-b bg-slate-50">
                <th className="text-left py-2 px-3">{fr ? 'Client' : 'Client'}</th>
                <th className="text-left py-2 px-3">{fr ? 'Type' : 'Type'}</th>
                <th className="text-right py-2 px-3">{fr ? 'Véhicules actifs' : 'Vehicles (active)'}</th>
                <th className="text-right py-2 px-3">{fr ? 'Brouillons' : 'Drafts'}</th>
                <th className="text-right py-2 px-3">{fr ? 'Marché' : 'Marketplace'}</th>
                <th className="text-right py-2 px-3">{fr ? 'Total' : 'Total'}</th>
                <th className="text-left py-2 px-3">{fr ? 'Statut' : 'Status'}</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c, idx) => (
                <tr key={c.id || idx} className="border-b" data-testid={`client-row-${c.id || idx}`}>
                  <td className="py-2 px-3">
                    <p className="font-medium">{c.name || c.id}</p>
                    <p className="text-xs text-slate-500 font-mono">{c.id?.slice(0, 8)}</p>
                  </td>
                  <td className="py-2 px-3"><Badge variant="outline">{c.account_type || '—'}</Badge></td>
                  <td className="py-2 px-3 text-right">{c.vehicle_active_count || 0}</td>
                  <td className="py-2 px-3 text-right">{(c.vehicle_draft_count || 0) + (c.marketplace_draft || 0)}</td>
                  <td className="py-2 px-3 text-right">{c.marketplace_active || 0}</td>
                  <td className="py-2 px-3 text-right font-semibold">{c.total_listings || 0}</td>
                  <td className="py-2 px-3">
                    {c.is_demo
                      ? <Badge className="bg-amber-100 text-amber-800">{fr ? 'Démo' : 'Demo'}</Badge>
                      : <Badge className="bg-emerald-100 text-emerald-800">{fr ? 'Actif' : 'Live'}</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Dashboard Mirror Tab ────────────────────────────────────────────

function DashboardTab({ data, fr }) {
  const e = data.earnings || {};
  const history = data.commission_history || [];
  return (
    <div className="space-y-3" data-testid="dashboard-mirror-tab">
      <Card>
        <CardContent className="p-4">
          <h3 className="font-semibold mb-3">{fr ? 'Gains' : 'Earnings'}</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label={fr ? 'Ce mois' : 'This month'} value={money(e.this_month_accrued)} testid="mirror-month" />
            <Stat label={fr ? 'Accumulé' : 'Accrued'} value={money(e.lifetime_accrued)} testid="mirror-accrued" />
            <Stat label={fr ? 'Versé' : 'Paid'} value={money(e.lifetime_paid)} testid="mirror-paid" />
            <Stat label={fr ? 'Entrées' : 'Entries'} value={e.entries_count || 0} testid="mirror-entries" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <h3 className="font-semibold mb-3">{fr ? 'Historique des commissions' : 'Commission history'}</h3>
          {history.length === 0 ? (
            <p className="text-sm text-slate-500" data-testid="mirror-history-empty">
              {fr ? 'Aucune entrée.' : 'No entries.'}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="mirror-history-table">
                <thead>
                  <tr className="text-xs text-slate-500 border-b">
                    <th className="text-left py-2 pr-2">{fr ? 'Date' : 'Date'}</th>
                    <th className="text-left py-2 pr-2">{fr ? 'Section' : 'Section'}</th>
                    <th className="text-right py-2 pr-2">{fr ? 'Taux' : 'Rate'}</th>
                    <th className="text-right py-2 pr-2">{fr ? 'Montant' : 'Amount'}</th>
                    <th className="text-left py-2 pr-2">{fr ? 'Statut' : 'Status'}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, idx) => (
                    <tr key={h.id || idx} className="border-b">
                      <td className="py-2 pr-2 text-xs">{h.created_at ? new Date(h.created_at).toLocaleDateString() : '—'}</td>
                      <td className="py-2 pr-2 text-xs">{h.section || '—'}</td>
                      <td className="py-2 pr-2 text-right text-xs">{((h.commission_rate_applied || h.rate || 0) * 100).toFixed(1)}%</td>
                      <td className="py-2 pr-2 text-right font-semibold">{money(h.commission_amount)}</td>
                      <td className="py-2 pr-2">
                        <Badge className={h.status === 'paid' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}>
                          {h.status || 'accrued'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value, testid }) {
  return (
    <div className="rounded-lg border p-3" data-testid={testid}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-bold">{value}</p>
    </div>
  );
}
