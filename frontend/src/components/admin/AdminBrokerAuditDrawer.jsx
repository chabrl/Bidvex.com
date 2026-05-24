/**
 * iter226 Task 2 — Admin Broker Audit Drawer (3 tabs).
 *
 *   • Deals & Escrow            — buyer linkages + Stripe $500 escrow ledger
 *   • Signed Legal Agreements   — exact IP / UA / timestamp / version
 *                                 for liability + custom contracts
 *   • Activity Log              — timeline of all platform footprints
 *
 * Fetches:
 *   GET /api/admin/brokers/{broker_id}/relationships
 *   GET /api/admin/brokers/{broker_id}/activity-log
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { X, ScrollText, DollarSign, Activity, RefreshCw, FileSignature, ShieldCheck, AlertTriangle, Clock } from 'lucide-react';

const TABS = [
  { id: 'deals',     en: 'Deals & Escrow',        fr: 'Affaires & Caution',   icon: DollarSign },
  { id: 'legal',     en: 'Signed Legal Agreements', fr: 'Accords légaux signés', icon: FileSignature },
  { id: 'activity',  en: 'Activity Log',          fr: 'Journal d\'activité',  icon: Activity },
];

const _fmt = (n) =>
  (n == null || Number.isNaN(Number(n)))
    ? '—'
    : new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n));

const _date = (v) => {
  if (!v) return '—';
  try { return new Date(v).toLocaleString(); } catch { return String(v); }
};

const DEPOSIT_COLOR = {
  pending:  'bg-slate-100 text-slate-700',
  held:     'bg-amber-100 text-amber-800',
  released: 'bg-blue-100 text-blue-800',
  captured: 'bg-rose-100 text-rose-800',
  refunded: 'bg-emerald-100 text-emerald-800',
  failed:   'bg-rose-200 text-rose-900',
};

const EVENT_COLOR = {
  ok:   'border-emerald-300 bg-emerald-50',
  warn: 'border-amber-300 bg-amber-50',
  info: 'border-blue-200 bg-blue-50',
  error:'border-rose-300 bg-rose-50',
};

export default function AdminBrokerAuditDrawer({ open, broker, onClose, lang = 'en' }) {
  const [tab, setTab] = useState('deals');
  const [relsData, setRelsData] = useState(null);
  const [activityData, setActivityData] = useState(null);
  const [loadingRels, setLoadingRels] = useState(false);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [error, setError] = useState(null);

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  useEffect(() => {
    if (!open || !broker?.id) return;
    setRelsData(null); setActivityData(null); setError(null); setTab('deals');
    let cancelled = false;
    (async () => {
      setLoadingRels(true);
      try {
        const r = await axios.get(`${API_BASE}/admin/brokers/${broker.id}/relationships`, {
          headers: { Authorization: `Bearer ${_token()}` },
        });
        if (!cancelled) setRelsData(r.data);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail?.error || 'failed_to_load');
      } finally { if (!cancelled) setLoadingRels(false); }
    })();
    (async () => {
      setLoadingActivity(true);
      try {
        const r = await axios.get(`${API_BASE}/admin/brokers/${broker.id}/activity-log?limit=500`, {
          headers: { Authorization: `Bearer ${_token()}` },
        });
        if (!cancelled) setActivityData(r.data);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail?.error || 'failed_to_load');
      } finally { if (!cancelled) setLoadingActivity(false); }
    })();
    return () => { cancelled = true; };
  }, [open, broker?.id]);

  const refresh = async () => {
    if (!broker?.id) return;
    setLoadingRels(true); setLoadingActivity(true);
    try {
      const [r1, r2] = await Promise.all([
        axios.get(`${API_BASE}/admin/brokers/${broker.id}/relationships`,  { headers: { Authorization: `Bearer ${_token()}` } }),
        axios.get(`${API_BASE}/admin/brokers/${broker.id}/activity-log?limit=500`, { headers: { Authorization: `Bearer ${_token()}` } }),
      ]);
      setRelsData(r1.data); setActivityData(r2.data);
    } catch (e) {
      setError(e?.response?.data?.detail?.error || 'refresh_failed');
    } finally {
      setLoadingRels(false); setLoadingActivity(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[90] bg-black/60 backdrop-blur-sm flex justify-end"
      onClick={onClose}
      data-testid="admin-broker-audit-drawer"
    >
      <div
        className="bg-white dark:bg-slate-900 w-full max-w-5xl h-full overflow-hidden flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="px-5 py-3 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h2 className="font-bold text-lg truncate" data-testid="audit-drawer-title">
              {broker.legal_business_name}
            </h2>
            <p className="text-xs opacity-90">
              {broker.operating_province} · {lang === 'fr' ? 'Licence' : 'Licence'} {broker.broker_license_number || '—'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={refresh}
              disabled={loadingRels || loadingActivity}
              className="p-1.5 rounded hover:bg-white/20 disabled:opacity-50"
              data-testid="audit-refresh"
              aria-label="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${(loadingRels || loadingActivity) ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-white/20"
              data-testid="audit-close"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Tabs */}
        <div className="border-b border-slate-200 dark:border-slate-700 px-3 bg-slate-50 dark:bg-slate-800 flex gap-1 overflow-x-auto" data-testid="audit-tabs">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-3 py-2.5 text-sm whitespace-nowrap flex items-center gap-1.5 border-b-2 transition ${
                  tab === t.id
                    ? 'border-[#1E3A8A] text-[#1E3A8A] dark:text-cyan-300 font-semibold'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                }`}
                data-testid={`audit-tab-${t.id}`}
              >
                <Icon className="w-4 h-4" />
                {lang === 'fr' ? t.fr : t.en}
              </button>
            );
          })}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 bg-slate-50 dark:bg-slate-900/40">
          {error && (
            <Card className="mb-4 border-rose-300 bg-rose-50" data-testid="audit-error"><CardContent className="p-3 text-rose-700 text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" /> {String(error)}
            </CardContent></Card>
          )}

          {tab === 'deals' && <DealsEscrowTab data={relsData} loading={loadingRels} lang={lang} />}
          {tab === 'legal' && <LegalAgreementsTab data={relsData} activity={activityData} loading={loadingRels || loadingActivity} lang={lang} />}
          {tab === 'activity' && <ActivityLogTab data={activityData} loading={loadingActivity} lang={lang} />}
        </div>
      </div>
    </div>
  );
}

// ── Tab 1 — Deals & Escrow ─────────────────────────────────────────────
function DealsEscrowTab({ data, loading, lang }) {
  if (loading) return <p className="text-center text-slate-500 py-8" data-testid="deals-loading">Loading…</p>;
  if (!data) return null;

  const c = data.counts || {};
  return (
    <section data-testid="audit-deals-tab" className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
        <MiniKpi label={lang === 'fr' ? 'Total' : 'Total'} value={c.total} testid="kpi-total" />
        <MiniKpi label={lang === 'fr' ? 'Actifs' : 'Active'} value={c.active} testid="kpi-active" accent="emerald" />
        <MiniKpi label={lang === 'fr' ? 'En attente' : 'Pending'} value={c.pending} testid="kpi-pending" accent="amber" />
        <MiniKpi label={lang === 'fr' ? 'Terminés' : 'Terminated'} value={c.terminated} testid="kpi-terminated" />
        <MiniKpi label={lang === 'fr' ? 'Rejetés' : 'Rejected'} value={c.rejected} testid="kpi-rejected" accent="rose" />
        <MiniKpi label={lang === 'fr' ? 'Détenus' : 'Deposits Held'} value={c.deposits_held} testid="kpi-held" accent="amber" />
        <MiniKpi label={lang === 'fr' ? 'Remboursés' : 'Refunded'} value={c.deposits_refunded} testid="kpi-refunded" accent="emerald" />
        <MiniKpi label={lang === 'fr' ? 'Libérés' : 'Released'} value={c.deposits_released} testid="kpi-released" accent="blue" />
      </div>

      {data.relationships.length === 0 ? (
        <Card data-testid="deals-empty"><CardContent className="p-8 text-center text-slate-500">
          {lang === 'fr' ? 'Aucune relation acheteur pour ce courtier.' : 'No buyer relationships for this broker.'}
        </CardContent></Card>
      ) : (
        <div className="space-y-2">
          {data.relationships.map((r) => (
            <Card key={r.relationship_id} data-testid={`audit-rel-row-${r.relationship_id}`}>
              <CardContent className="p-3">
                <div className="flex items-start gap-3 flex-wrap">
                  <div className="flex-1 min-w-[220px]">
                    <div className="font-semibold text-slate-900 dark:text-white">
                      {r.buyer_full_name || r.buyer_email}
                    </div>
                    <div className="text-xs text-slate-500">{r.buyer_email}</div>
                    <div className="flex gap-1.5 mt-1.5 flex-wrap">
                      <Badge className="bg-slate-100 text-slate-700">{r.status}</Badge>
                      <Badge className={DEPOSIT_COLOR[r.escrow?.deposit_status] || 'bg-slate-100 text-slate-700'}>
                        $ {r.escrow?.deposit_status || '—'}
                      </Badge>
                      <Badge variant="outline">{r.bid_count} {lang === 'fr' ? 'mises' : 'bids'}</Badge>
                      {r.custom_terms?.accepted_at && (
                        <Badge className="bg-emerald-100 text-emerald-800">
                          {lang === 'fr' ? 'Contrat accepté' : 'Contract accepted'}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="text-right text-xs text-slate-500">
                    <div>{lang === 'fr' ? 'Créé' : 'Created'}: {_date(r.created_at)}</div>
                    <div>{lang === 'fr' ? 'MAJ' : 'Updated'}: {_date(r.updated_at)}</div>
                  </div>
                </div>

                {/* Escrow ledger */}
                <div className="mt-3 p-2.5 rounded border border-amber-200 bg-amber-50 dark:bg-amber-950/30 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div><div className="text-slate-500">{lang === 'fr' ? 'Montant' : 'Amount'}</div><div className="font-mono font-semibold">{_fmt(r.escrow?.deposit_amount_cad)}</div></div>
                  <div><div className="text-slate-500">PI ID</div><div className="font-mono text-[10px] truncate">{r.escrow?.deposit_stripe_payment_intent_id || '—'}</div></div>
                  <div><div className="text-slate-500">{lang === 'fr' ? 'Bloqué le' : 'Held at'}</div><div className="text-[11px]">{_date(r.escrow?.deposit_held_at)}</div></div>
                  <div><div className="text-slate-500">{lang === 'fr' ? 'Libéré le' : 'Released at'}</div><div className="text-[11px]">{_date(r.escrow?.deposit_released_at)}</div></div>
                  {r.escrow?.deposit_refund_result && (
                    <div className="col-span-2 sm:col-span-4 text-[11px] mt-1 text-amber-900 dark:text-amber-200">
                      <span className="font-semibold">{lang === 'fr' ? 'Résultat Stripe' : 'Stripe result'}:</span> {r.escrow.deposit_refund_result.action}
                      {r.escrow.deposit_refund_result.refund_id ? ` · refund_id=${r.escrow.deposit_refund_result.refund_id}` : ''}
                    </div>
                  )}
                </div>

                {/* Bid cap + rejection / suspension reasons */}
                {(r.max_bid_amount_cad != null || r.rejection_reason || r.suspended_reason) && (
                  <div className="mt-2 text-xs text-slate-600 dark:text-slate-300">
                    {r.max_bid_amount_cad != null && (
                      <div>{lang === 'fr' ? 'Plafond enchère' : 'Bid cap'}: <span className="font-mono">{_fmt(r.max_bid_amount_cad)}</span></div>
                    )}
                    {r.rejection_reason && <div className="text-rose-600">{lang === 'fr' ? 'Rejet' : 'Reject'}: {r.rejection_reason}</div>}
                    {r.suspended_reason && <div className="text-orange-600">{lang === 'fr' ? 'Suspendu' : 'Suspended'}: {r.suspended_reason}</div>}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

// ── Tab 2 — Signed Legal Agreements ────────────────────────────────────
function LegalAgreementsTab({ data, activity, loading, lang }) {
  if (loading) return <p className="text-center text-slate-500 py-8" data-testid="legal-loading">Loading…</p>;

  // Liability signatures from activity log (kind starts with "legal:")
  const legalEvents = (activity?.events || []).filter((e) => (e.kind || '').startsWith('legal:'));

  // Custom-terms acceptances from relationships
  const acceptances = (data?.relationships || []).filter((r) => r.custom_terms?.accepted_at);

  return (
    <section className="space-y-5" data-testid="audit-legal-tab">
      {/* Platform Liability Contract */}
      <div>
        <h3 className="font-semibold mb-2 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-rose-600" />
          {lang === 'fr' ? 'Contrat de responsabilité plateforme' : 'Platform Liability Contract'}
        </h3>
        {legalEvents.length === 0 ? (
          <Card data-testid="legal-no-liability"><CardContent className="p-4 text-sm text-slate-500">
            {lang === 'fr' ? 'Aucune signature enregistrée.' : 'No signatures on record.'}
          </CardContent></Card>
        ) : (
          <div className="space-y-2">
            {legalEvents.map((e, i) => (
              <Card key={`legal-${i}`} data-testid={`legal-sig-${i}`} className="border-l-4 border-l-rose-500">
                <CardContent className="p-3">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <div className="font-semibold text-sm font-serif italic" data-testid={`legal-sig-name-${i}`}>
                        ✍ {e.details?.signature_full_name || '—'}
                      </div>
                      <div className="text-xs text-slate-500">
                        v: {e.details?.agreement_version || '—'} · {lang === 'fr' ? 'Locale' : 'Locale'}: {e.details?.locale || '—'} · {lang === 'fr' ? 'Étape' : 'Stage'}: {e.details?.stage || '—'}
                      </div>
                    </div>
                    <div className="text-right text-xs text-slate-500">
                      <div className="flex items-center gap-1 justify-end"><Clock className="w-3 h-3" /> {_date(e.at)}</div>
                    </div>
                  </div>
                  <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                    <div className="font-mono p-2 rounded bg-slate-100 dark:bg-slate-800">
                      <span className="text-slate-500">IP:</span> {e.details?.signed_ip || '—'}
                    </div>
                    <div className="font-mono p-2 rounded bg-slate-100 dark:bg-slate-800 truncate" title={e.details?.signed_user_agent}>
                      <span className="text-slate-500">UA:</span> {e.details?.signed_user_agent || '—'}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Custom Broker-Buyer contract acceptances */}
      <div>
        <h3 className="font-semibold mb-2 flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-amber-600" />
          {lang === 'fr' ? 'Contrats acheteurs personnalisés' : 'Buyer Custom Contract Acceptances'}
        </h3>
        {acceptances.length === 0 ? (
          <Card data-testid="legal-no-custom-terms"><CardContent className="p-4 text-sm text-slate-500">
            {lang === 'fr' ? 'Aucune acceptation enregistrée.' : 'No acceptances on record.'}
          </CardContent></Card>
        ) : (
          <div className="space-y-2">
            {acceptances.map((r) => (
              <Card key={r.relationship_id} data-testid={`legal-accept-${r.relationship_id}`} className="border-l-4 border-l-amber-500">
                <CardContent className="p-3">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="min-w-0">
                      <div className="font-semibold text-sm" data-testid={`legal-accept-buyer-${r.relationship_id}`}>
                        {r.buyer_full_name || r.buyer_email}
                      </div>
                      <div className="text-xs text-slate-500">{r.buyer_email}</div>
                      <div className="font-serif italic text-sm mt-1">
                        ✍ {r.custom_terms?.acceptance?.signature_text || '—'}
                      </div>
                    </div>
                    <div className="text-right text-xs text-slate-500">
                      <div className="flex items-center gap-1 justify-end"><Clock className="w-3 h-3" /> {_date(r.custom_terms?.accepted_at)}</div>
                      <div className="text-[10px]">{lang === 'fr' ? 'Mise à jour' : 'Updated'}: {_date(r.custom_terms?.broker_terms_updated_at)}</div>
                    </div>
                  </div>
                  <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                    <div className="font-mono p-2 rounded bg-slate-100 dark:bg-slate-800">
                      <span className="text-slate-500">IP:</span> {r.custom_terms?.acceptance?.accepted_ip || '—'}
                    </div>
                    <div className="font-mono p-2 rounded bg-slate-100 dark:bg-slate-800 truncate" title={r.custom_terms?.acceptance?.accepted_user_agent}>
                      <span className="text-slate-500">UA:</span> {r.custom_terms?.acceptance?.accepted_user_agent || '—'}
                    </div>
                  </div>
                  {/* Show the actual HTML they consented to */}
                  {r.custom_terms?.broker_terms_html ? (
                    <details className="mt-2 text-xs">
                      <summary className="cursor-pointer text-blue-600 hover:underline" data-testid={`legal-accept-show-html-${r.relationship_id}`}>
                        {lang === 'fr' ? 'Voir le contenu HTML signé' : 'Show signed HTML content'}
                      </summary>
                      <div
                        className="mt-2 p-3 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 prose prose-sm dark:prose-invert max-w-none"
                        dangerouslySetInnerHTML={{ __html: r.custom_terms.broker_terms_html }}
                        data-testid={`legal-accept-html-${r.relationship_id}`}
                      />
                    </details>
                  ) : r.custom_terms?.broker_terms_plain ? (
                    <details className="mt-2 text-xs">
                      <summary className="cursor-pointer text-blue-600 hover:underline">
                        {lang === 'fr' ? 'Voir le contenu texte signé' : 'Show signed text content'}
                      </summary>
                      <pre className="mt-2 p-3 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 whitespace-pre-wrap font-sans">{r.custom_terms.broker_terms_plain}</pre>
                    </details>
                  ) : null}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

// ── Tab 3 — Activity Log Timeline ─────────────────────────────────────
function ActivityLogTab({ data, loading, lang }) {
  if (loading) return <p className="text-center text-slate-500 py-8" data-testid="activity-loading">Loading…</p>;
  if (!data) return null;
  const events = data.events || [];

  if (events.length === 0) {
    return (
      <Card data-testid="activity-empty"><CardContent className="p-8 text-center text-slate-500">
        {lang === 'fr' ? 'Aucune activité enregistrée.' : 'No activity recorded.'}
      </CardContent></Card>
    );
  }

  return (
    <section data-testid="audit-activity-tab">
      <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-600" />
          {lang === 'fr' ? 'Chronologie complète' : 'Full Activity Timeline'}
        </h3>
        <span className="text-xs text-slate-500">{events.length} {lang === 'fr' ? 'événements' : 'events'}</span>
      </div>
      <Card><CardContent className="p-0">
        <table className="w-full text-sm" data-testid="activity-table">
          <thead>
            <tr className="text-left text-xs text-slate-500 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
              <th className="py-2 px-3 w-[180px]">{lang === 'fr' ? 'Quand' : 'When'}</th>
              <th className="px-3 w-[200px]">{lang === 'fr' ? 'Événement' : 'Event'}</th>
              <th className="px-3">{lang === 'fr' ? 'Détails' : 'Details'}</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={`evt-${i}`} className={`border-b border-slate-100 dark:border-slate-800 ${EVENT_COLOR[e.severity] || ''}`} data-testid={`activity-row-${i}`}>
                <td className="py-2 px-3 text-[11px] font-mono align-top whitespace-nowrap">{_date(e.at)}</td>
                <td className="px-3 align-top">
                  <code className="text-[11px]">{e.kind}</code>
                </td>
                <td className="px-3 align-top text-xs">
                  <div>{e.message}</div>
                  {e.details && (
                    <details className="mt-1 text-[11px] text-slate-600 dark:text-slate-300">
                      <summary className="cursor-pointer">…</summary>
                      <pre className="mt-1 p-2 bg-white/60 dark:bg-slate-900/50 rounded text-[10px] overflow-x-auto">{JSON.stringify(e.details, null, 2)}</pre>
                    </details>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent></Card>
    </section>
  );
}

function MiniKpi({ label, value, accent, testid }) {
  const accentMap = {
    emerald: 'text-emerald-700',
    amber:   'text-amber-700',
    rose:    'text-rose-700',
    blue:    'text-blue-700',
  };
  return (
    <Card data-testid={testid}><CardContent className="p-2 text-center">
      <div className={`text-lg font-bold tabular-nums ${accentMap[accent] || ''}`}>{value ?? 0}</div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500 leading-tight">{label}</div>
    </CardContent></Card>
  );
}
