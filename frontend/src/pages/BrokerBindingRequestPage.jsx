/**
 * iter217 Phase 5 Hotfix v8 — Buyer → Broker partnership request.
 *
 * Route: /brokers/:broker_id/request
 *
 * v8 fixes:
 *   • Reads the new v7 fee-engine response shape (nested `summary`,
 *     `hammer_settlement`, `stripe_processing_fee`).
 *   • Every numeric field is null-guarded — no more
 *     `Cannot read property 'toFixed' of undefined` crashes.
 *   • Fee preview rendered as TWO clearly separated sections:
 *       A) Vehicle Hammer Price — direct settlement (amber)
 *       B) BidVex Service Fees — Stripe-charged (blue)
 *     plus a refundable deposit row and a final total.
 *   • The Stripe processing fee is read straight from the API; no
 *     client-side recalculation. Hammer NEVER enters the Stripe total.
 *
 * Flow:
 *   1. Loads the broker's public profile + a $15,000 fee preview.
 *   2. Buyer reviews legal copy + the $500 CAD security deposit.
 *   3. Click "Authorize Deposit" → POST /api/broker-relationships/request
 *      → backend creates relationship + Stripe PaymentIntent
 *      (capture_method=manual). Card is held, not charged.
 */
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import API_BASE from '../config';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import {
  ShieldCheck, Lock, AlertTriangle, CheckCircle2, ChevronLeft,
  CircleDollarSign, CreditCard, BadgeCheck,
} from 'lucide-react';
import BuyerCustomTermsModal from '../components/broker/BuyerCustomTermsModal';

const _fmt = (n) =>
  (n == null || Number.isNaN(Number(n)))
    ? '—'
    : new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n));

function Row({ label, value, accent, bold, big, muted, testId }) {
  return (
    <div className="flex justify-between items-baseline py-1" data-testid={testId}>
      <span className={`text-sm ${muted ? 'text-slate-400' : 'text-slate-700 dark:text-slate-200'}`}>{label}</span>
      <span className={`tabular-nums ${big ? 'text-xl font-bold text-[#1E3A8A] dark:text-cyan-300'
                                            : bold ? 'font-semibold text-blue-700 dark:text-cyan-300'
                                                   : accent ? 'font-semibold text-amber-700 dark:text-amber-300'
                                                            : 'text-slate-900 dark:text-white'}`}>
        {value}
      </span>
    </div>
  );
}

export default function BrokerBindingRequestPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const navigate = useNavigate();
  const { broker_id } = useParams();

  const [broker, setBroker]     = useState(null);
  const [feeData, setFeeData]   = useState(null);
  const [province, setProvince] = useState('ON');
  const [submitting, setSubmit] = useState(false);
  const [error, setError]       = useState(null);
  const [success, setSuccess]   = useState(false);
  // iter225 Task 4 — Custom Terms gating
  const [customTerms, setCustomTerms]       = useState(null);
  const [termsAccepted, setTermsAccepted]   = useState(false);
  const [termsSignature, setTermsSignature] = useState(null);
  const [termsModalOpen, setTermsModalOpen] = useState(false);
  // iter229 — optional buyer-set bid cap
  const [bidCap, setBidCap] = useState('');

  // Load broker custom terms in parallel so we know whether to gate the deposit click
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/brokers/${broker_id}/custom-terms`);
        if (!cancelled) setCustomTerms(r.data);
      } catch (e) {
        if (!cancelled) setCustomTerms({ enabled: false });
      }
    })();
    return () => { cancelled = true; };
  }, [broker_id]);

  // ─── Load broker + initial fee preview ──────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/brokers/${broker_id}`);
        if (!cancelled) setBroker(r.data);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail?.error || 'failed_to_load_broker');
      }
    })();
    return () => { cancelled = true; };
  }, [broker_id]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r2 = await axios.post(`${API_BASE}/brokers/${broker_id}/fee-preview`, {
          hammer_price: 15000, buyer_province: province,
        });
        if (!cancelled) setFeeData(r2.data);
      } catch (e) {
        // Non-fatal — keep the page usable
        if (!cancelled) console.error('[fee-preview] failed', e);
      }
    })();
    return () => { cancelled = true; };
  }, [broker_id, province]);

  const needsCustomTerms = !!(customTerms?.enabled && (customTerms.custom_terms_html?.trim() || customTerms.custom_terms_plain?.trim()));
  const canAuthorize = !needsCustomTerms || termsAccepted;

  // ─── Authorize $500 hold ────────────────────────────────────
  const authorizeDeposit = async () => {
    // iter225 Task 4 — if broker has custom terms enabled, force the modal first
    if (needsCustomTerms && !termsAccepted) {
      setTermsModalOpen(true);
      return;
    }
    setSubmit(true); setError(null);
    try {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      const r = await axios.post(
        `${API_BASE}/broker-relationships/request`,
        { broker_id },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (r.data?.success) {
        // iter229 — set optional bid cap right after relationship creation
        if (bidCap && r.data?.relationship_id) {
          try {
            await axios.patch(
              `${API_BASE}/broker-relationships/${r.data.relationship_id}/bid-cap`,
              { bid_cap: parseFloat(bidCap) },
              { headers: { Authorization: `Bearer ${token}` } },
            );
          } catch (e) { console.error('[bid-cap] failed', e); }
        }
        // iter225 Task 4 — Post acceptance against the new relationship_id
        if (needsCustomTerms && termsSignature && r.data?.relationship_id) {
          try {
            await axios.post(
              `${API_BASE}/broker-relationships/${r.data.relationship_id}/accept-custom-terms`,
              { accepted: true, signature_text: termsSignature, locale: lang },
              { headers: { Authorization: `Bearer ${token}` } },
            );
          } catch (e) {
            console.error('[custom-terms-accept] post-failed', e);
          }
        }
        setSuccess(true);
        setTimeout(() => navigate('/account?tab=broker'), 2000);
      }
    } catch (e) {
      setError(
        e?.response?.data?.detail?.[lang === 'fr' ? 'message_fr' : 'message_en']
        || e?.response?.data?.detail?.error
        || 'Request failed',
      );
    } finally {
      setSubmit(false);
    }
  };

  if (success) {
    return (
      <div className="container mx-auto max-w-2xl py-12 px-4">
        <Card><CardContent className="p-8 text-center" data-testid="broker-request-success">
          <CheckCircle2 className="mx-auto h-16 w-16 text-emerald-500 mb-4" />
          <h1 className="text-2xl font-bold mb-2">
            {lang === 'fr' ? 'Demande envoyée !' : 'Request sent!'}
          </h1>
          <p className="text-slate-600 dark:text-slate-300">
            {lang === 'fr'
              ? 'Votre dépôt de 500 $ est conservé en toute sécurité. Votre courtier examinera votre demande sous peu.'
              : 'Your $500 deposit is held securely. Your broker will review your request shortly.'}
          </p>
        </CardContent></Card>
      </div>
    );
  }

  if (!broker) {
    return <div className="container mx-auto max-w-2xl py-12 px-4 text-center text-slate-500">Loading…</div>;
  }

  const depositAmount = Number(broker.default_deposit_amount_cad || 500);

  // ─── Extract v7 fields with null guards ─────────────────────
  const f = feeData || {};
  const hammer       = f.hammer_price;
  const platformFee  = f.platform_fee;
  const brokerFee    = f.broker_fee;
  const gst          = f.gst;
  const qst          = f.qst;
  const stripeFee    = f.stripe_processing_fee;
  const stripeTotal  = f.summary?.buyer_pays_stripe ?? f.stripe_total_charged;
  const directTotal  = f.summary?.buyer_pays_direct ?? hammer;
  const grandTotal   = f.summary?.buyer_total_cost  ?? ((stripeTotal != null && directTotal != null) ? stripeTotal + directTotal : null);

  return (
    <div className="container mx-auto max-w-3xl py-8 px-4">
      <Button variant="ghost" onClick={() => navigate(-1)} className="mb-4" data-testid="broker-request-back">
        <ChevronLeft className="h-4 w-4 mr-1" />{lang === 'fr' ? 'Retour' : 'Back'}
      </Button>

      <h1 className="text-3xl font-bold mb-2">{broker.legal_business_name}</h1>
      <p className="text-slate-600 dark:text-slate-300 mb-6">
        {broker.operating_province} · {broker.regulatory_body} · {lang === 'fr' ? 'Licence' : 'License'} {broker.broker_license_number_masked}
      </p>

      {/* ── Province selector for accurate preview ─────────────── */}
      <Card className="mb-4">
        <CardContent className="p-4 flex items-center justify-between gap-3 flex-wrap">
          <div>
            <p className="font-semibold text-sm">
              {lang === 'fr' ? 'Votre province d\'acheteur' : 'Your buyer province'}
            </p>
            <p className="text-xs text-slate-500">
              {lang === 'fr' ? 'Affecte le calcul de la TVQ' : 'Affects QST calculation'}
            </p>
          </div>
          <Select value={province} onValueChange={setProvince}>
            <SelectTrigger className="w-[200px]" data-testid="binding-province-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="QC">Quebec / Québec</SelectItem>
              <SelectItem value="ON">Ontario</SelectItem>
              <SelectItem value="AB">Alberta</SelectItem>
              <SelectItem value="BC">British Columbia / C.-B.</SelectItem>
              <SelectItem value="MB">Manitoba</SelectItem>
              <SelectItem value="SK">Saskatchewan</SelectItem>
              <SelectItem value="NS">Nova Scotia</SelectItem>
              <SelectItem value="OTHER">{lang === 'fr' ? 'Autre' : 'Other'}</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* ── Two-section fee preview ────────────────────────────── */}
      <Card className="mb-4 overflow-hidden" data-testid="broker-fee-preview-card">
        <CardContent className="p-0">
          <div className="px-5 py-3 bg-slate-100 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
            <h2 className="font-semibold text-slate-900 dark:text-white text-sm">
              {lang === 'fr' ? 'Aperçu des frais (sur 15 000 $)' : 'Fee Preview (based on $15,000 sample)'}
            </h2>
          </div>

          {/* SECTION A — VEHICLE HAMMER (DIRECT) */}
          <div className="bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-900 px-5 py-4">
            <p className="text-[10px] font-bold uppercase tracking-wider text-amber-700 dark:text-amber-300 mb-2">
              {lang === 'fr' ? 'Section A — Prix marteau du véhicule' : 'Section A — Vehicle Hammer Price'}
            </p>
            <Row
              label={lang === 'fr' ? `Prix marteau ${'\u00a0'}(direct)` : `Hammer Price ${'\u00a0'}(direct)`}
              value={_fmt(hammer)}
              accent
              testId="fee-row-hammer"
            />
            <div className="mt-2 flex items-start gap-2 text-xs text-amber-800 dark:text-amber-200">
              <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
              <span>
                {lang === 'fr'
                  ? 'Réglé directement entre vous et votre courtier par virement bancaire ou chèque certifié. BidVex ne traite pas ce montant.'
                  : 'Settled directly between you and your broker via bank wire or certified cheque. BidVex does not process this amount.'}
              </span>
            </div>
          </div>

          {/* SECTION B — STRIPE-CHARGED SERVICE FEES */}
          <div className="bg-blue-50 dark:bg-blue-950/30 px-5 py-4">
            <p className="text-[10px] font-bold uppercase tracking-wider text-blue-700 dark:text-cyan-300 mb-2">
              {lang === 'fr' ? 'Section B — Frais de service (via Stripe)' : 'Section B — BidVex Service Fees (via Stripe)'}
            </p>
            <Row label={lang === 'fr' ? 'Frais de plateforme BidVex (2,5 %)' : 'BidVex Platform Fee (2.5%)'} value={_fmt(platformFee)} testId="fee-row-platform" />
            <Row label={lang === 'fr' ? 'Frais de service du courtier' : 'Broker Service Fee'} value={_fmt(brokerFee)} testId="fee-row-broker" />
            <Row label={lang === 'fr' ? 'TPS (5 %)' : 'GST (5%)'} value={_fmt(gst)} testId="fee-row-gst" />
            {(qst != null && Number(qst) > 0) && (
              <Row label={lang === 'fr' ? 'TVQ (9,975 %) [QC uniquement]' : 'QST (9.975%) [QC only]'} value={_fmt(qst)} testId="fee-row-qst" />
            )}
            <Row label={lang === 'fr' ? 'Frais de traitement Stripe' : 'Stripe Processing Fee'} value={_fmt(stripeFee)} testId="fee-row-stripe-proc" />
            <div className="border-t border-blue-200 dark:border-blue-800 mt-2 pt-2">
              <Row
                label={lang === 'fr' ? 'Vous payez via Stripe' : 'You Pay via Stripe'}
                value={_fmt(stripeTotal)}
                bold
                testId="fee-row-stripe-total"
              />
            </div>
          </div>

          {/* DEPOSIT */}
          <div className="bg-slate-50 dark:bg-slate-800 px-5 py-3 border-t border-slate-200 dark:border-slate-700">
            <Row
              label={
                <span className="flex items-center gap-1.5 flex-wrap">
                  <Lock className="h-3.5 w-3.5" />
                  {lang === 'fr' ? 'Caution de sécurité (remboursable)' : 'Security Deposit (refundable)'}
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-500 text-white text-[9px] font-bold uppercase tracking-wide" data-testid="refundable-badge-fee-row">
                    {lang === 'fr' ? '100 %' : '100%'}
                  </span>
                </span>
              }
              value={_fmt(depositAmount)}
              testId="fee-row-deposit"
            />
            <p className="text-[11px] text-slate-500 mt-0.5">
              {lang === 'fr' ? 'Garantie 100 % remboursable — libérée à la résiliation du partenariat ou à la remise du véhicule.' : '100% refundable guarantee — released on partnership termination or vehicle handoff.'}
            </p>
          </div>

          {/* GRAND TOTAL */}
          <div className="bg-gradient-to-r from-blue-100 to-cyan-100 dark:from-blue-950 dark:to-cyan-950 px-5 py-4 border-t-2 border-[#1E3A8A]/20">
            <Row
              label={lang === 'fr' ? 'Coût total estimé' : 'Total Estimated Cost'}
              value={_fmt(grandTotal)}
              big
              testId="fee-row-grand-total"
            />
            <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">
              {lang === 'fr' ? 'Stripe' : 'Stripe'} {_fmt(stripeTotal)} + {lang === 'fr' ? 'Direct' : 'Direct'} {_fmt(directTotal)}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* ── Deposit notice ─────────────────────────────────────── */}
      <Card className="border-2 border-amber-300 bg-amber-50 dark:bg-amber-950/30 mb-4">
        <CardContent className="p-5 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <CircleDollarSign className="h-5 w-5 text-amber-600" />
            <h2 className="font-semibold">{lang === 'fr' ? 'Dépôt de garantie requis' : 'Security Deposit Required'}</h2>
            {/* iter225 Task 5 — 100% Refundable Guarantee badge */}
            <span
              className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500 text-white text-[11px] font-bold tracking-wide shadow"
              data-testid="refundable-badge-header"
            >
              <BadgeCheck className="w-3.5 h-3.5" />
              {lang === 'fr' ? '100 % REMBOURSABLE' : '100% REFUNDABLE'}
            </span>
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {lang === 'fr'
              ? `Un dépôt remboursable de ${depositAmount} $ CAD est requis pour s'associer à un courtier. Ce dépôt est conservé de manière sécurisée via Stripe et vérifie votre engagement en tant qu'acheteur sérieux. Il sera remboursé intégralement à la fin de notre partenariat, sauf si vous remportez un véhicule et ne complétez pas le paiement.`
              : `A refundable deposit of $${depositAmount} CAD is required to partner with a broker. This deposit is held securely via Stripe and verifies your commitment as a serious buyer. It is fully refunded when our partnership ends, unless you win a vehicle and fail to complete payment.`}
          </p>
          {/* iter225 Task 5 — 3-row guarantee block */}
          <ul className="text-xs text-slate-700 dark:text-slate-200 space-y-1 pl-1">
            <li className="flex items-start gap-2"><BadgeCheck className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" /> {lang === 'fr' ? 'Aucun frais aujourd\'hui — la carte est seulement bloquée.' : 'No charge today — card is only authorized (held).'}</li>
            <li className="flex items-start gap-2"><BadgeCheck className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" /> {lang === 'fr' ? 'Remboursé automatiquement via Stripe à la fin du partenariat.' : 'Automatically refunded via Stripe when the partnership ends.'}</li>
            <li className="flex items-start gap-2"><BadgeCheck className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" /> {lang === 'fr' ? 'Traité par Stripe — BidVex ne conserve jamais votre carte.' : 'Processed by Stripe — BidVex never stores your card.'}</li>
          </ul>
          <div className="text-lg font-bold flex items-center gap-2 flex-wrap">
            <span>{lang === 'fr' ? 'Montant du dépôt' : 'Deposit Amount'}: ${depositAmount.toFixed(2)} CAD</span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold uppercase" data-testid="refundable-badge-amount">
              {lang === 'fr' ? 'Garantie 100 %' : '100% Guarantee'}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* iter229 — Optional buyer-defined bid cap */}
      <Card className="border-2 border-slate-200 dark:border-slate-700 mb-4" data-testid="bid-cap-form-card">
        <CardContent className="p-4">
          <label htmlFor="bid_cap" className="block text-sm font-semibold text-slate-700 dark:text-slate-200 mb-1">
            {lang === 'fr' ? 'Définir un plafond budgétaire (optionnel)' : 'Set a maximum budget cap (optional)'}
          </label>
          <p className="text-xs text-slate-500 mb-3">
            {lang === 'fr'
              ? 'Votre courtier ne pourra pas placer d\'enchères au-dessus de ce montant en votre nom, toutes enchères confondues. Laissez vide pour aucun plafond.'
              : 'Your broker cannot place bids above this amount on your behalf across all auctions. Leave blank for no cap.'}
          </p>
          <div className="relative rounded-md shadow-sm max-w-xs">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <span className="text-slate-500 sm:text-sm">$</span>
            </div>
            <input
              type="number"
              name="bid_cap"
              id="bid_cap"
              min="1"
              placeholder={lang === 'fr' ? 'Illimité' : 'Unlimited'}
              value={bidCap || ''}
              onChange={(e) => setBidCap(e.target.value)}
              className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-7 pr-12 sm:text-sm border border-slate-300 dark:border-slate-700 dark:bg-slate-900 rounded-md py-2"
              data-testid="bid-cap-input"
            />
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
              <span className="text-slate-500 sm:text-sm">CAD</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* iter227 Fix #2 — Custom Contract rendered INLINE & PROMINENTLY */}
      {needsCustomTerms && (
        <Card className={`border-2 mb-4 ${termsAccepted ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-950/30' : 'border-amber-400 bg-white dark:bg-slate-900'}`} data-testid="broker-custom-contract-banner">
          <CardContent className="p-0">
            <div className={`px-5 py-3 ${termsAccepted ? 'bg-emerald-500' : 'bg-gradient-to-r from-amber-500 to-orange-500'} text-white flex items-center gap-2 flex-wrap`}>
              <CircleDollarSign className="w-5 h-5 flex-shrink-0" />
              <h2 className="font-bold flex-1 min-w-0">
                {lang === 'fr' ? 'Contrat sur mesure du courtier — à lire' : "Broker's Custom Contract — Required Reading"}
              </h2>
              {termsAccepted && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white text-emerald-700 text-[11px] font-bold uppercase tracking-wide" data-testid="custom-terms-accepted-badge">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {lang === 'fr' ? 'Accepté' : 'Accepted'}
                </span>
              )}
            </div>
            <div className="p-5 space-y-4">
              <p className="text-sm text-slate-700 dark:text-slate-200">
                {lang === 'fr'
                  ? 'Ce courtier exige que vous acceptiez les conditions ci-dessous AVANT de pouvoir verser le dépôt de 500 $ et placer des enchères. Lisez-les attentivement.'
                  : 'This broker requires you to accept the terms below BEFORE you can authorize the $500 deposit and place any bids. Read carefully.'}
              </p>
              {/* INLINE rendered custom contract — always visible */}
              <div
                className="rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 p-4 max-h-[420px] overflow-y-auto text-sm prose prose-sm dark:prose-invert max-w-none"
                data-testid="broker-custom-terms-inline"
              >
                {customTerms?.custom_terms_html?.trim() ? (
                  <div dangerouslySetInnerHTML={{ __html: customTerms.custom_terms_html }} />
                ) : (
                  <pre className="whitespace-pre-wrap font-sans m-0">{customTerms?.custom_terms_plain || ''}</pre>
                )}
              </div>

              {/* Acceptance row */}
              {!termsAccepted ? (
                <div className="space-y-3">
                  <Button
                    onClick={() => setTermsModalOpen(true)}
                    className="w-full bg-gradient-to-r from-amber-500 to-orange-500 text-white"
                    data-testid="open-custom-terms"
                  >
                    {lang === 'fr' ? 'Lire en plein écran et signer' : 'Read Full-Screen & Sign'}
                  </Button>
                  <p className="text-[11px] text-amber-700 dark:text-amber-300 text-center">
                    {lang === 'fr'
                      ? 'L\'acceptation est obligatoire avant de pouvoir débloquer le dépôt.'
                      : 'Acceptance is required before the deposit button unlocks.'}
                  </p>
                </div>
              ) : (
                <Alert className="border-emerald-300 bg-emerald-50">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <AlertDescription className="text-emerald-800">
                    {lang === 'fr'
                      ? `Vous avez signé le contrat${termsSignature ? ` (${termsSignature})` : ''}. Vous pouvez maintenant autoriser le dépôt.`
                      : `You've signed the contract${termsSignature ? ` (${termsSignature})` : ''}. You can now authorize the deposit.`}
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription data-testid="broker-request-error">{String(error)}</AlertDescription>
        </Alert>
      )}

      <Button
        onClick={authorizeDeposit}
        disabled={submitting || !canAuthorize}
        className="w-full bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white"
        data-testid="broker-authorize-deposit"
      >
        <ShieldCheck className="h-5 w-5 mr-2" />
        {submitting
          ? (lang === 'fr' ? 'En cours...' : 'Processing...')
          : !canAuthorize
            ? (lang === 'fr' ? 'Acceptez d\'abord le contrat du courtier' : 'Accept the broker contract first')
            : (lang === 'fr' ? `Autoriser le dépôt — 100 % remboursable, vous ne serez pas débité maintenant` : `Authorize Deposit — 100% Refundable, no charge today`)}
      </Button>

      <p className="text-xs text-center text-slate-500 mt-3 flex items-center justify-center gap-1.5">
        <CreditCard className="h-3 w-3" />
        {lang === 'fr'
          ? 'BidVex ne stocke pas vos informations de carte. Tout le traitement des paiements est géré par Stripe.'
          : 'BidVex does not store your card information. All payment processing is handled by Stripe.'}
      </p>

      {/* iter225 Task 4 — Buyer Custom Terms Modal */}
      <BuyerCustomTermsModal
        open={termsModalOpen}
        brokerId={broker_id}
        relationshipId={null /* not yet created — will accept post-creation */}
        lang={lang}
        onClose={() => setTermsModalOpen(false)}
        onAccepted={(result) => {
          setTermsAccepted(true);
          setTermsSignature(result?.signature_text || null);
          setTermsModalOpen(false);
        }}
      />
    </div>
  );
}
