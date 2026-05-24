/**
 * iter228 — Buyer-side "My Active Broker Partnership" panel.
 *
 * Renders a comprehensive management environment when the authenticated
 * buyer is bound to an approved broker. Replaces the generic "Request
 * Partnership" CTA on /brokers when a relationship exists.
 *
 * Tabs:
 *   • Overview     — jurisdiction + license + fee structure + signed terms
 *   • Active Bids  — live broker_bids placed on the buyer's behalf
 *   • Purchases    — won + closed vehicles with payment/release state
 *
 * Termination ("Resign From Broker") includes the obligation gate from
 * GET /broker-relationships/my-active-broker → termination.can_terminate.
 *
 * Data source: GET /api/broker-relationships/my-active-broker
 * Termination: POST /api/broker-relationships/{rel_id}/buyer-terminate
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Alert, AlertDescription } from '../ui/alert';
import {
  Handshake, ShieldCheck, MapPin, Banknote, FileText, Activity,
  Receipt, Clock, AlertTriangle, CheckCircle2, XCircle, Lock,
  BadgeCheck, Loader2, LogOut, Calendar,
} from 'lucide-react';

const _fmt = (n) =>
  (n == null || Number.isNaN(Number(n)))
    ? '$0'
    : new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n));

const _date = (v) => {
  if (!v) return '—';
  try { return new Date(v).toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' }); }
  catch { return String(v); }
};

const _dateTime = (v) => {
  if (!v) return '—';
  try { return new Date(v).toLocaleString(); }
  catch { return String(v); }
};

// Province → regulator label map for badge rendering
const PROV_REGS = {
  QC: [{ k: 'ANQ',   field: 'qc_anq_number' }, { k: 'OPC',   field: 'qc_opc_number' }],
  ON: [{ k: 'OMVIC', field: 'on_omvic_number' }],
  BC: [{ k: 'VSA',   field: 'bc_vsa_number' }],
  AB: [{ k: 'AMVIC', field: 'ab_amvic_number' }],
};

const TABS = [
  { id: 'overview',  icon: ShieldCheck, en: 'Overview',     fr: 'Aperçu' },
  { id: 'bids',      icon: Activity,    en: 'Active Bids',  fr: 'Enchères actives' },
  { id: 'purchases', icon: Receipt,     en: 'Purchases',    fr: 'Achats' },
];

export default function MyActiveBrokerPanel({ lang = 'en' }) {
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [tab, setTab]           = useState('overview');
  const [terminating, setTerminating] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [termError, setTermError]     = useState(null);
  const [termSuccess, setTermSuccess] = useState(null);

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await axios.get(`${API_BASE}/broker-relationships/my-active-broker`, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      setData(r.data?.data || null);
    } catch (e) {
      // 401 simply means not logged in; treat as no partnership
      if (e?.response?.status === 401) {
        setData(null);
      } else {
        setError(e?.response?.data?.detail?.error || 'failed_to_load');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-500 py-3" data-testid="my-broker-loading">
        <Loader2 className="w-4 h-4 animate-spin" />
        {lang === 'fr' ? 'Vérification du partenariat...' : 'Checking partnership...'}
      </div>
    );
  }

  // No active partnership — return null so the parent renders its normal directory
  if (!data) return null;

  const rel = data.relationship;
  const b   = data.broker || {};
  const termination = data.termination || {};

  const prov = PROV_REGS[b.operating_province] || [];

  const submitTerminate = async () => {
    setTerminating(true); setTermError(null); setTermSuccess(null);
    try {
      const r = await axios.post(
        `${API_BASE}/broker-relationships/${rel.id}/buyer-terminate`,
        {},
        { headers: { Authorization: `Bearer ${_token()}` } },
      );
      setTermSuccess(r.data?.[lang === 'fr' ? 'message_fr' : 'message_en']
                     || 'Partnership terminated.');
      setConfirmOpen(false);
      // Re-load to clear the panel (data will be null now)
      setTimeout(load, 800);
    } catch (e) {
      setTermError(
        e?.response?.data?.detail?.[lang === 'fr' ? 'message_fr' : 'message_en']
        || e?.response?.data?.detail?.error
        || 'termination_failed'
      );
    } finally {
      setTerminating(false);
    }
  };

  return (
    <section className="mb-8" data-testid="my-active-broker-panel">
      <Card className="border-2 border-emerald-300 bg-gradient-to-br from-emerald-50 to-cyan-50 dark:from-emerald-950/40 dark:to-cyan-950/40 overflow-hidden shadow-lg">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white px-5 py-4 flex items-center gap-3 flex-wrap">
          <div className="rounded-full p-2 bg-white/15">
            <Handshake className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="font-bold text-base sm:text-lg" data-testid="my-broker-title">
              {lang === 'fr' ? 'Mon partenariat de courtage actif' : 'My Active Broker Partnership'}
            </h2>
            <p className="text-xs opacity-90 truncate">
              {b.legal_business_name} · {lang === 'fr' ? 'depuis' : 'since'} {_date(rel.created_at)}
            </p>
          </div>
          <Badge className="bg-emerald-400 text-emerald-950 font-bold uppercase text-[10px]" data-testid="my-broker-status-badge">
            <BadgeCheck className="w-3 h-3 mr-1" />
            {(rel.status === 'active') ? (lang === 'fr' ? 'Actif' : 'Active') : rel.status}
          </Badge>
        </div>

        {/* Tabs */}
        <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 px-3 flex gap-1 overflow-x-auto" data-testid="my-broker-tabs">
          {TABS.map((t) => {
            const Icon = t.icon;
            const count = t.id === 'bids' ? (data.active_bids || []).length
                        : t.id === 'purchases' ? (data.purchases || []).length
                        : null;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-3 py-2.5 text-sm whitespace-nowrap flex items-center gap-1.5 border-b-2 transition ${
                  tab === t.id
                    ? 'border-[#1E3A8A] text-[#1E3A8A] dark:text-cyan-300 font-semibold'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                }`}
                data-testid={`my-broker-tab-${t.id}`}
              >
                <Icon className="w-4 h-4" />
                {lang === 'fr' ? t.fr : t.en}
                {count != null && count > 0 && (
                  <span className="ml-1 px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold">{count}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Tab body */}
        <CardContent className="p-5 bg-white dark:bg-slate-900">
          {tab === 'overview' && (
            <OverviewTab b={b} rel={rel} prov={prov} lang={lang} />
          )}
          {tab === 'bids' && (
            <ActiveBidsTab bids={data.active_bids || []} lang={lang} />
          )}
          {tab === 'purchases' && (
            <PurchasesTab purchases={data.purchases || []} lang={lang} />
          )}

          {/* Termination block — always visible at the bottom */}
          <TerminationBlock
            termination={termination}
            confirmOpen={confirmOpen}
            setConfirmOpen={setConfirmOpen}
            terminating={terminating}
            termError={termError}
            termSuccess={termSuccess}
            onConfirm={submitTerminate}
            lang={lang}
          />
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive" className="mt-3">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{String(error)}</AlertDescription>
        </Alert>
      )}
    </section>
  );
}

// ── Overview tab ───────────────────────────────────────────────────────
function OverviewTab({ b, rel, prov, lang }) {
  const fee = b.fee_structure;
  const isPct = fee?.type === 'percentage';
  return (
    <div className="space-y-5" data-testid="my-broker-overview">
      {/* Jurisdiction & License */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-800/40">
          <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
            <MapPin className="w-4 h-4 text-blue-600" />
            {lang === 'fr' ? 'Juridiction' : 'Jurisdiction'}
          </h3>
          <div className="flex flex-wrap gap-1.5 mb-2" data-testid="my-broker-jurisdiction-badges">
            <Badge className="bg-blue-100 text-blue-800">
              {b.operating_province} · {b.regulatory_body}
            </Badge>
            {prov.map((p) => b[p.field] ? (
              <Badge key={p.k} className="bg-blue-100 text-blue-800 font-mono text-[10px]">
                {p.k}: {b[p.field]}
              </Badge>
            ) : null)}
          </div>
          <p className="text-xs text-slate-500">
            {lang === 'fr'
              ? `Autorisé à enchérir en votre nom en ${b.operating_province} sous la réglementation ${b.regulatory_body}.`
              : `Licensed to bid on your behalf in ${b.operating_province} under ${b.regulatory_body} regulation.`}
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-800/40">
          <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            {lang === 'fr' ? 'Statut & Licence' : 'Status & Licence'}
          </h3>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">{lang === 'fr' ? 'Licence' : 'Licence #'}</span>
              <span className="font-mono font-semibold" data-testid="my-broker-license-number">{b.broker_license_number || '—'}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">{lang === 'fr' ? 'Inscription' : 'Registration #'}</span>
              <span className="font-mono">{b.corporate_registration_number || '—'}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">{lang === 'fr' ? 'Approuvé le' : 'Approved on'}</span>
              <span data-testid="my-broker-verified-at">{_date(b.verified_at)}</span>
            </div>
            <div className="flex items-center gap-1.5 pt-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-emerald-700 dark:text-emerald-300 font-medium">
                {lang === 'fr' ? 'Opérationnel & vérifié' : 'Operational & verified'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Fee structure */}
      <div className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950/30 p-4" data-testid="my-broker-fee-block">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-2">
          <Banknote className="w-4 h-4 text-amber-700" />
          {lang === 'fr' ? 'Structure de commission convenue' : 'Agreed Commission Structure'}
        </h3>
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="text-3xl font-bold text-amber-700 dark:text-amber-300 tabular-nums">
            {isPct ? `${(Number(fee?.percentage_rate || 0) * 100).toFixed(2)}%` : _fmt(fee?.fixed_amount_cad)}
          </span>
          <span className="text-sm text-slate-600 dark:text-slate-300">
            {isPct
              ? (lang === 'fr' ? 'du prix marteau' : 'of hammer price')
              : (lang === 'fr' ? 'fixe par lot gagné' : 'fixed per winning lot')}
          </span>
        </div>
        {(fee?.min_fee_cad || fee?.max_fee_cad) && (
          <p className="text-xs text-slate-500 mt-1.5">
            {fee.min_fee_cad ? `Min ${_fmt(fee.min_fee_cad)}` : ''}
            {fee.min_fee_cad && fee.max_fee_cad ? ' · ' : ''}
            {fee.max_fee_cad ? `Max ${_fmt(fee.max_fee_cad)}` : ''}
          </p>
        )}
        {rel.max_bid_amount_cad != null && (
          <p className="text-xs text-slate-600 dark:text-slate-300 mt-1.5">
            {lang === 'fr' ? 'Plafond d\'enchère convenu' : 'Agreed bid cap'}: <span className="font-mono font-semibold">{_fmt(rel.max_bid_amount_cad)}</span>
          </p>
        )}
      </div>

      {/* Deposit */}
      <div className="rounded-lg border border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30 p-4 flex items-center gap-3 flex-wrap" data-testid="my-broker-deposit-block">
        <Lock className="w-5 h-5 text-emerald-600 flex-shrink-0" />
        <div className="flex-1 min-w-[200px]">
          <p className="font-semibold text-sm">
            {lang === 'fr' ? 'Dépôt de garantie 100 % remboursable' : '100% Refundable Security Deposit'}
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            {_fmt(rel.deposit_amount_cad || 500)} · {lang === 'fr' ? 'Statut' : 'Status'}: <strong>{rel.deposit_status || '—'}</strong>
          </p>
        </div>
        <Badge className="bg-emerald-500 text-white font-bold">{rel.deposit_status || '—'}</Badge>
      </div>

      {/* Signed custom terms */}
      {(b.custom_terms_enabled && (b.custom_terms_html?.trim() || b.custom_terms_plain?.trim())) && (
        <div className="rounded-lg border border-slate-300 dark:border-slate-700 overflow-hidden" data-testid="my-broker-signed-terms">
          <div className="px-4 py-2.5 bg-slate-100 dark:bg-slate-800 flex items-center justify-between gap-2 flex-wrap">
            <h3 className="font-semibold text-sm flex items-center gap-2">
              <FileText className="w-4 h-4 text-blue-600" />
              {lang === 'fr' ? 'Contrat signé du courtier' : "Broker's Signed Contract"}
            </h3>
            {rel.custom_terms_accepted_at ? (
              <span className="inline-flex items-center gap-1 text-emerald-700 text-[11px] font-semibold" data-testid="my-broker-signed-at">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {lang === 'fr' ? 'Signé le' : 'Signed on'} {_dateTime(rel.custom_terms_accepted_at)}
              </span>
            ) : (
              <span className="text-[11px] text-amber-600">
                {lang === 'fr' ? 'Non signé' : 'Not yet signed'}
              </span>
            )}
          </div>
          <div className="max-h-[300px] overflow-y-auto p-4 text-sm prose prose-sm dark:prose-invert max-w-none" data-testid="my-broker-terms-html">
            {b.custom_terms_html ? (
              <div dangerouslySetInnerHTML={{ __html: b.custom_terms_html }} />
            ) : (
              <pre className="whitespace-pre-wrap font-sans m-0">{b.custom_terms_plain}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Active bids tab ────────────────────────────────────────────────────
function ActiveBidsTab({ bids, lang }) {
  if (bids.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500" data-testid="my-broker-no-bids">
        <Activity className="w-10 h-10 mx-auto mb-2 opacity-30" />
        <p className="text-sm">
          {lang === 'fr'
            ? 'Aucune enchère active sous ce courtier pour le moment.'
            : 'No active bids placed under this broker right now.'}
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-2" data-testid="my-broker-bids-list">
      {bids.map((bid) => {
        const top = bid.listing?.we_are_top;
        return (
          <div
            key={bid.bid_id}
            className={`rounded-lg border-2 p-3 flex gap-3 ${top ? 'border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30' : 'border-amber-300 bg-amber-50 dark:bg-amber-950/30'}`}
            data-testid={`my-broker-bid-${bid.bid_id}`}
          >
            {bid.listing?.image && (
              <img src={bid.listing.image} alt="" className="w-20 h-20 rounded object-cover flex-shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <h4 className="font-semibold text-sm truncate">{bid.listing?.title || `Listing ${bid.vehicle_listing_id?.slice(0, 8)}`}</h4>
              <div className="flex flex-wrap items-center gap-2 mt-1 text-xs">
                <span className="text-slate-500">{lang === 'fr' ? 'Notre mise' : 'Our bid'}:</span>
                <span className="font-mono font-bold">{_fmt(bid.bid_amount_cad)}</span>
                <span className="text-slate-500">·</span>
                <span className="text-slate-500">{lang === 'fr' ? 'Mise actuelle' : 'Current bid'}:</span>
                <span className="font-mono">{_fmt(bid.listing?.current_bid)}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-1.5">
                {top ? (
                  <Badge className="bg-emerald-500 text-white text-[10px]">
                    <BadgeCheck className="w-3 h-3 mr-1" />
                    {lang === 'fr' ? 'En tête' : 'Top Bid'}
                  </Badge>
                ) : (
                  <Badge className="bg-amber-500 text-white text-[10px]">
                    {lang === 'fr' ? 'Surenchéri' : 'Outbid'}
                  </Badge>
                )}
                <Badge variant="outline" className="text-[10px]">
                  <Clock className="w-3 h-3 mr-1" />
                  {lang === 'fr' ? 'Fin' : 'Ends'} {_dateTime(bid.listing?.ends_at)}
                </Badge>
              </div>
            </div>
            <a
              href={`/vehicle/${bid.vehicle_listing_id}`}
              className="text-blue-600 text-xs font-semibold hover:underline flex-shrink-0 self-start"
              data-testid={`my-broker-bid-link-${bid.bid_id}`}
            >
              {lang === 'fr' ? 'Voir →' : 'View →'}
            </a>
          </div>
        );
      })}
    </div>
  );
}

// ── Purchases tab ──────────────────────────────────────────────────────
function PurchasesTab({ purchases, lang }) {
  if (purchases.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500" data-testid="my-broker-no-purchases">
        <Receipt className="w-10 h-10 mx-auto mb-2 opacity-30" />
        <p className="text-sm">
          {lang === 'fr'
            ? 'Aucun véhicule encore acheté via ce courtier.'
            : 'No vehicles purchased through this broker yet.'}
        </p>
      </div>
    );
  }
  return (
    <div className="overflow-x-auto" data-testid="my-broker-purchases-list">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-500 border-b border-slate-200 dark:border-slate-700">
            <th className="py-2 px-2">{lang === 'fr' ? 'Véhicule' : 'Vehicle'}</th>
            <th className="px-2">VIN</th>
            <th className="px-2 text-right">{lang === 'fr' ? 'Marteau' : 'Hammer'}</th>
            <th className="px-2 text-right">{lang === 'fr' ? 'Commission' : 'Commission'}</th>
            <th className="px-2 text-right">{lang === 'fr' ? 'Total' : 'Total'}</th>
            <th className="px-2">{lang === 'fr' ? 'Paiement' : 'Payment'}</th>
            <th className="px-2">{lang === 'fr' ? 'Remise' : 'Release'}</th>
          </tr>
        </thead>
        <tbody>
          {purchases.map((p) => (
            <tr key={p.invoice_id} className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40" data-testid={`my-broker-purchase-${p.invoice_id}`}>
              <td className="py-2 px-2">
                <div className="flex items-center gap-2">
                  {p.image && <img src={p.image} alt="" className="w-10 h-10 rounded object-cover flex-shrink-0" />}
                  <div className="min-w-0">
                    <div className="font-medium truncate">{p.vehicle_title || '—'}</div>
                    <div className="text-[10px] text-slate-400">{p.invoice_number}</div>
                  </div>
                </div>
              </td>
              <td className="px-2 font-mono text-[11px]">{p.vin || '—'}</td>
              <td className="px-2 text-right font-mono">{_fmt(p.hammer_price_cad)}</td>
              <td className="px-2 text-right font-mono text-amber-700">{_fmt(p.broker_fee_cad)}</td>
              <td className="px-2 text-right font-mono font-bold">{_fmt(p.total_cad)}</td>
              <td className="px-2">
                {p.payment_status === 'paid' ? (
                  <Badge className="bg-emerald-100 text-emerald-800"><CheckCircle2 className="w-3 h-3 mr-1" />{lang === 'fr' ? 'Payé' : 'Paid'}</Badge>
                ) : (
                  <Badge className="bg-amber-100 text-amber-800"><Clock className="w-3 h-3 mr-1" />{lang === 'fr' ? 'En attente' : 'Pending'}</Badge>
                )}
              </td>
              <td className="px-2">
                {p.released ? (
                  <Badge className="bg-blue-100 text-blue-800">
                    <Calendar className="w-3 h-3 mr-1" />
                    {_date(p.released_at)}
                  </Badge>
                ) : <span className="text-slate-400 text-[11px]">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Termination block ──────────────────────────────────────────────────
function TerminationBlock({ termination, confirmOpen, setConfirmOpen, terminating, termError, termSuccess, onConfirm, lang }) {
  const canTerminate = !!termination?.can_terminate;
  const reasons      = termination?.block_reasons || [];

  return (
    <div className="mt-6 pt-5 border-t-2 border-dashed border-rose-200 dark:border-rose-900" data-testid="my-broker-termination-block">
      <h3 className="font-semibold text-sm flex items-center gap-2 mb-3 text-rose-700 dark:text-rose-400">
        <LogOut className="w-4 h-4" />
        {lang === 'fr' ? 'Mettre fin au partenariat' : 'End Partnership'}
      </h3>

      {!canTerminate ? (
        <Alert variant="destructive" className="mb-3" data-testid="my-broker-cannot-terminate-alert">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <p className="font-semibold mb-1">
              {lang === 'fr'
                ? 'Impossible de mettre fin au partenariat tant que des enchères sont actives ou que des factures sont en attente de règlement.'
                : 'Cannot terminate partnership while bids are active or invoices are pending settlement.'}
            </p>
            <ul className="text-xs space-y-0.5 mt-2">
              {reasons.map((r) => (
                <li key={r.code} data-testid={`my-broker-block-reason-${r.code}`}>
                  • {r.code === 'active_bids'
                       ? (lang === 'fr' ? `${r.count} enchère(s) active(s)` : `${r.count} active bid(s)`)
                       : (lang === 'fr' ? `${r.count} facture(s) en attente` : `${r.count} pending invoice(s)`)}
                </li>
              ))}
            </ul>
            <p className="text-xs mt-2 italic">
              {lang === 'fr'
                ? 'Réglez ces obligations avant de pouvoir résilier.'
                : 'Settle these obligations before you can resign.'}
            </p>
          </AlertDescription>
        </Alert>
      ) : (
        <p className="text-xs text-slate-500 mb-3">
          {lang === 'fr'
            ? 'Aucune obligation en attente. Vous pouvez mettre fin à ce partenariat en toute sécurité. Votre dépôt de 500 $ sera remboursé automatiquement via Stripe.'
            : 'No outstanding obligations. You can safely end this partnership. Your $500 deposit will be automatically refunded via Stripe.'}
        </p>
      )}

      {termError && (
        <Alert variant="destructive" className="mb-3">
          <XCircle className="h-4 w-4" />
          <AlertDescription data-testid="my-broker-term-error">{String(termError)}</AlertDescription>
        </Alert>
      )}
      {termSuccess && (
        <Alert className="mb-3 border-emerald-300 bg-emerald-50">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <AlertDescription className="text-emerald-800" data-testid="my-broker-term-success">{termSuccess}</AlertDescription>
        </Alert>
      )}

      {!confirmOpen ? (
        <Button
          variant="outline"
          onClick={() => setConfirmOpen(true)}
          disabled={!canTerminate || terminating || termSuccess}
          className="border-rose-400 text-rose-700 hover:bg-rose-50 hover:text-rose-800 disabled:opacity-50"
          data-testid="my-broker-terminate-btn"
        >
          <LogOut className="w-4 h-4 mr-2" />
          {lang === 'fr' ? 'Résigner du courtier' : 'Resign From Broker'}
        </Button>
      ) : (
        <div className="rounded-lg border-2 border-rose-400 bg-rose-50 dark:bg-rose-950/30 p-4 space-y-3" data-testid="my-broker-confirm-block">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm font-semibold">
              {lang === 'fr'
                ? 'Êtes-vous absolument certain de vouloir mettre fin à ce partenariat ?'
                : 'Are you absolutely sure you want to end this partnership?'}
            </p>
          </div>
          <p className="text-xs text-slate-700 dark:text-slate-200">
            {lang === 'fr'
              ? 'Cette action est immédiate. Votre dépôt de 500 $ sera remboursé via Stripe. Vous et le courtier recevrez un courriel de confirmation.'
              : 'This action takes effect immediately. Your $500 deposit will be refunded via Stripe. Both you and the broker will receive an email confirmation.'}
          </p>
          <div className="flex gap-2 flex-wrap">
            <Button
              onClick={onConfirm}
              disabled={terminating || !canTerminate}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="my-broker-terminate-confirm"
            >
              {terminating
                ? (lang === 'fr' ? 'En cours...' : 'Terminating...')
                : (lang === 'fr' ? 'Oui, mettre fin au partenariat' : 'Yes, end the partnership')}
            </Button>
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={terminating}
              data-testid="my-broker-terminate-cancel"
            >
              {lang === 'fr' ? 'Annuler' : 'Cancel'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
