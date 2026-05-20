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
  CircleDollarSign, CreditCard,
} from 'lucide-react';

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

  // ─── Authorize $500 hold ────────────────────────────────────
  const authorizeDeposit = async () => {
    setSubmit(true); setError(null);
    try {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      const r = await axios.post(
        `${API_BASE}/broker-relationships/request`,
        { broker_id },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (r.data?.success) {
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
                <span className="flex items-center gap-1.5">
                  <Lock className="h-3.5 w-3.5" />
                  {lang === 'fr' ? 'Caution de sécurité (remboursable)' : 'Security Deposit (refundable)'}
                </span>
              }
              value={_fmt(depositAmount)}
              testId="fee-row-deposit"
            />
            <p className="text-[11px] text-slate-500 mt-0.5">
              {lang === 'fr' ? 'Libérée après la remise du véhicule' : 'Released after vehicle handoff'}
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
          <div className="flex items-center gap-2">
            <CircleDollarSign className="h-5 w-5 text-amber-600" />
            <h2 className="font-semibold">{lang === 'fr' ? 'Dépôt de garantie requis' : 'Security Deposit Required'}</h2>
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {lang === 'fr'
              ? `Un dépôt remboursable de ${depositAmount} $ CAD est requis pour s'associer à un courtier. Ce dépôt est conservé de manière sécurisée via Stripe et vérifie votre engagement en tant qu'acheteur sérieux. Il sera remboursé intégralement à la fin de notre partenariat, sauf si vous remportez un véhicule et ne complétez pas le paiement.`
              : `A refundable deposit of $${depositAmount} CAD is required to partner with a broker. This deposit is held securely via Stripe and verifies your commitment as a serious buyer. It is fully refunded when our partnership ends, unless you win a vehicle and fail to complete payment.`}
          </p>
          <div className="text-lg font-bold">
            {lang === 'fr' ? 'Montant du dépôt' : 'Deposit Amount'}: ${depositAmount.toFixed(2)} CAD
          </div>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription data-testid="broker-request-error">{String(error)}</AlertDescription>
        </Alert>
      )}

      <Button
        onClick={authorizeDeposit}
        disabled={submitting}
        className="w-full bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white"
        data-testid="broker-authorize-deposit"
      >
        <ShieldCheck className="h-5 w-5 mr-2" />
        {submitting
          ? (lang === 'fr' ? 'En cours...' : 'Processing...')
          : (lang === 'fr' ? `Autoriser le dépôt — vous ne serez pas débité maintenant` : `Authorize Deposit — You won't be charged now`)}
      </Button>

      <p className="text-xs text-center text-slate-500 mt-3 flex items-center justify-center gap-1.5">
        <CreditCard className="h-3 w-3" />
        {lang === 'fr'
          ? 'BidVex ne stocke pas vos informations de carte. Tout le traitement des paiements est géré par Stripe.'
          : 'BidVex does not store your card information. All payment processing is handled by Stripe.'}
      </p>
    </div>
  );
}
