/**
 * iter211 P3 — Vehicle Dealer Annual Fee Banner
 *
 * Shown to approved vehicle dealers on the seller dashboard:
 *   ▸ NO subscription yet → "Activate Your Dealer Account" prominent banner
 *     with "Pay Annual Fee — $100.00/yr" CTA → opens Stripe Checkout.
 *   ▸ ACTIVE subscription  → small renewal-info card (collapsed).
 *   ▸ SUSPENDED / expired  → "Renew now" amber banner.
 *
 * Bilingual EN/FR via i18next language detection.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Loader2, KeyRound, CheckCircle2, AlertTriangle, CreditCard } from 'lucide-react';
import API_BASE from '../config';

const DealerAnnualFeeBanner = ({ user }) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    let alive = true;
    if (!user?.is_vehicle_dealer) { setLoading(false); return; }
    axios.get(`${API_BASE}/dealer-subscription/status`)
      .then(r => { if (alive) setStatus(r.data); })
      .catch(() => { if (alive) setStatus(null); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [user?.id, user?.is_vehicle_dealer]);

  // Show toast based on `?dealer_fee=success|cancelled` after Stripe redirect
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('dealer_fee') === 'success') {
      // refresh status
      axios.get(`${API_BASE}/dealer-subscription/status`).then(r => setStatus(r.data)).catch(() => {});
    }
  }, []);

  if (!user?.is_vehicle_dealer) return null;
  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500 flex items-center gap-2 mb-4" data-testid="dealer-fee-banner-loading">
        <Loader2 className="w-3 h-3 animate-spin" />
        {isFr ? 'Vérification de votre abonnement…' : 'Checking your subscription…'}
      </div>
    );
  }

  // Demo accounts never see this banner; backend blocks Stripe calls anyway
  if (status?.is_demo_account) return null;

  const handlePay = async () => {
    try {
      setPaying(true);
      const r = await axios.post(`${API_BASE}/dealer-subscription/create-checkout-session`);
      if (r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
      } else if (r.data?.already_active) {
        setStatus({ ...status, active: true });
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Dealer checkout failed:', e);
      alert(isFr ? "Échec du paiement. Veuillez réessayer." : 'Payment failed. Please try again.');
    } finally {
      setPaying(false);
    }
  };

  // SCENARIO A — Not yet paid (most prominent)
  if (!status?.active && !status?.suspended) {
    return (
      <div
        data-testid="dealer-fee-banner-pay"
        className="rounded-2xl border-2 border-amber-300 bg-gradient-to-r from-amber-50 via-amber-50 to-yellow-50 p-6 mb-6 shadow-sm"
      >
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
            <KeyRound className="w-6 h-6 text-amber-700" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-bold text-amber-900" data-testid="dealer-fee-banner-title">
              {isFr ? 'Activez votre compte concessionnaire' : 'Activate Your Dealer Account'}
            </h3>
            <p className="text-sm text-amber-800 mt-1 leading-relaxed">
              {isFr
                ? 'Votre demande est approuvée ! Complétez votre abonnement annuel pour commencer à lister vos véhicules sur BidVex.'
                : 'Your application is approved! Complete your annual platform subscription to start listing vehicles on BidVex.'}
            </p>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-sm text-amber-700 line-through">$200.00/yr</span>
              <span className="text-2xl font-bold text-amber-900">$100.00/yr</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-200 text-amber-900 font-medium">
                {isFr ? 'Offre de lancement -50 %' : 'Launch offer −50%'}
              </span>
            </div>
            <p className="text-[11px] text-amber-700 mt-1">
              {isFr ? 'TPS + TVQ ou TVH appliquées au passage en caisse' : 'GST + QST or HST applied at checkout'}
            </p>
            <button
              onClick={handlePay}
              disabled={paying}
              data-testid="dealer-fee-pay-btn"
              className="mt-4 inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold shadow-sm transition-colors disabled:opacity-50"
            >
              {paying ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CreditCard className="w-4 h-4" />
              )}
              {isFr ? 'Payer les frais — 100,00 $/an' : 'Pay Annual Fee — $100.00/yr'}
            </button>
            <p className="text-[11px] text-amber-700 mt-3">
              {isFr ? 'Questions ? partners@bidvex.ca' : 'Questions? partners@bidvex.ca'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // SCENARIO C — Suspended / expired (prominent amber)
  if (status?.suspended) {
    return (
      <div
        data-testid="dealer-fee-banner-suspended"
        className="rounded-2xl border-2 border-rose-300 bg-gradient-to-r from-rose-50 to-amber-50 p-6 mb-6"
      >
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-full bg-rose-100 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-6 h-6 text-rose-700" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-rose-900">
              {isFr ? 'Votre abonnement a expiré' : 'Your subscription has lapsed'}
            </h3>
            <p className="text-sm text-rose-800 mt-1">
              {isFr
                ? 'Renouvelez maintenant pour réactiver vos annonces.'
                : 'Renew now to reactivate your listings.'}
            </p>
            <button
              onClick={handlePay}
              disabled={paying}
              data-testid="dealer-fee-renew-btn"
              className="mt-4 inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm font-semibold shadow-sm transition-colors disabled:opacity-50"
            >
              {paying ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
              {isFr ? 'Renouveler — 100,00 $/an' : 'Renew — $100.00/yr'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // SCENARIO B — Active (small info card, collapsible)
  const renewal = status?.renewal_date ? new Date(status.renewal_date).toLocaleDateString(isFr ? 'fr-CA' : 'en-CA', { year: 'numeric', month: 'short', day: 'numeric' }) : '—';
  return (
    <div
      data-testid="dealer-fee-banner-active"
      className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 mb-4 flex items-center justify-between text-sm"
    >
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
        <span className="text-emerald-900 font-medium">
          {isFr ? 'Accès plateforme — Actif' : 'Platform Access — Active'}
        </span>
        <span className="text-emerald-700 text-xs">
          · {isFr ? `Renouvellement : ${renewal}` : `Renews: ${renewal}`}
        </span>
      </div>
      <span className="text-xs text-emerald-700 font-mono">$100.00/yr</span>
    </div>
  );
};

export default DealerAnnualFeeBanner;
export { DealerAnnualFeeBanner };
