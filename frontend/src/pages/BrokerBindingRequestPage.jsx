/**
 * iter217 Phase 5 Hotfix v5b — Buyer → Broker partnership request.
 *
 * Route: /brokers/:broker_id/request
 *
 * Flow:
 *   1. Loads the broker's public profile + a $15,000 fee preview.
 *   2. Buyer reviews legal copy + the $500 CAD security deposit notice.
 *   3. Click "Authorize Deposit" → POST /api/broker-relationships/request
 *      → backend creates relationship + Stripe PaymentIntent (capture
 *      method = manual). Card is held, not charged.
 *   4. Buyer is redirected to a "waiting for broker approval" page.
 *
 * NOTE: Stripe Card Element wiring for SCA-authentication is scoped for
 * Hotfix v6 — the MVP currently relies on Stripe's `automatic_payment_methods`
 * webhook flow + buyer follow-up in their Stripe portal if 3DS is needed.
 */
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import API_BASE from '../config';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Alert, AlertDescription } from '../components/ui/alert';
import { ShieldCheck, Lock, AlertTriangle, CheckCircle2, ChevronLeft } from 'lucide-react';

export default function BrokerBindingRequestPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const navigate = useNavigate();
  const { broker_id } = useParams();

  const [broker, setBroker]     = useState(null);
  const [feePreview, setFee]    = useState(null);
  const [submitting, setSubmit] = useState(false);
  const [error, setError]       = useState(null);
  const [success, setSuccess]   = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/brokers/${broker_id}`);
        if (!cancelled) setBroker(r.data);
        const r2 = await axios.post(`${API_BASE}/brokers/${broker_id}/fee-preview`, {
          hammer_price: 15000, buyer_province: 'ON',
        });
        if (!cancelled) setFee(r2.data);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail?.error || 'failed_to_load_broker');
      }
    })();
    return () => { cancelled = true; };
  }, [broker_id]);

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

  return (
    <div className="container mx-auto max-w-3xl py-8 px-4">
      <Button variant="ghost" onClick={() => navigate(-1)} className="mb-4" data-testid="broker-request-back">
        <ChevronLeft className="h-4 w-4 mr-1" />{lang === 'fr' ? 'Retour' : 'Back'}
      </Button>

      <h1 className="text-3xl font-bold mb-2">{broker.legal_business_name}</h1>
      <p className="text-slate-600 dark:text-slate-300 mb-6">
        {broker.operating_province} · {broker.regulatory_body} · {lang === 'fr' ? 'Licence' : 'License'} {broker.broker_license_number_masked}
      </p>

      {feePreview && (
        <Card className="mb-4 bg-slate-50 dark:bg-slate-900" data-testid="broker-fee-preview-card">
          <CardContent className="p-5">
            <h2 className="font-semibold mb-3">{lang === 'fr' ? 'Aperçu des frais (sur 15 000 $)' : 'Fee preview (on $15,000)'}</h2>
            <div className="text-sm space-y-1 font-mono">
              <div className="flex justify-between"><span>{lang === 'fr' ? 'Prix final' : 'Hammer price'}</span><span>${feePreview.hammer_price_cad.toFixed(2)}</span></div>
              <div className="flex justify-between"><span>{lang === 'fr' ? 'Frais BidVex (2,5 %)' : 'BidVex platform fee (2.5%)'}</span><span>+${feePreview.bidvex_platform_fee_cad.toFixed(2)}</span></div>
              <div className="flex justify-between"><span>{lang === 'fr' ? 'Frais du courtier' : 'Broker fee'}</span><span>+${feePreview.broker_fee_cad.toFixed(2)}</span></div>
              <div className="flex justify-between"><span>{lang === 'fr' ? 'TPS (5 %)' : 'GST (5%)'}</span><span>+${feePreview.gst_cad.toFixed(2)}</span></div>
              {feePreview.qst_cad > 0 && <div className="flex justify-between"><span>{lang === 'fr' ? 'TVQ (9,975 %)' : 'QST (9.975%)'}</span><span>+${feePreview.qst_cad.toFixed(2)}</span></div>}
              <div className="flex justify-between"><span>{lang === 'fr' ? 'Traitement Stripe' : 'Stripe processing'}</span><span>+${feePreview.stripe_fee_cad.toFixed(2)}</span></div>
              <div className="border-t pt-2 mt-2 flex justify-between font-bold"><span>{lang === 'fr' ? 'Total' : 'Total'}</span><span>${feePreview.total_cad.toFixed(2)}</span></div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="border-2 border-amber-300 bg-amber-50 dark:bg-amber-950/30 mb-4">
        <CardContent className="p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-amber-600" />
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

      <p className="text-xs text-center text-slate-500 mt-3">
        {lang === 'fr'
          ? 'BidVex ne stocke pas vos informations de carte. Tout le traitement des paiements est géré par Stripe.'
          : 'BidVex does not store your card information. All payment processing is handled by Stripe.'}
      </p>
    </div>
  );
}
