/**
 * GlobalDealerFeeBanner — iter214 P3
 *
 * FULL-WIDTH STICKY banner shown across EVERY page when a vehicle dealer
 * has no active subscription (or it expired / was suspended).
 *
 * Requirements:
 *   - Sits above the navbar (position: sticky, top: 0, z-index: 9999)
 *   - Cannot be dismissed
 *   - Disappears the moment subscription becomes active
 *   - Bilingual EN / FR simultaneously
 *
 * Mounted once at the top of <App /> so it's visible on every route.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { CreditCard, Lock, Loader2 } from 'lucide-react';
import API_BASE from '../config';

const GlobalDealerFeeBanner = () => {
  const { user, token } = useAuth();
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);

  const fetchStatus = useCallback(async () => {
    if (!user?.is_vehicle_dealer || !token) {
      setLoading(false);
      return;
    }
    try {
      const r = await axios.get(`${API_BASE}/dealer-subscription/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStatus(r.data);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [user?.is_vehicle_dealer, token]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  // Refresh on Stripe-checkout redirect (?dealer_fee=success)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('dealer_fee') === 'success') fetchStatus();
  }, [fetchStatus]);

  if (loading) return null;
  if (!user?.is_vehicle_dealer) return null;
  if (status?.is_demo_account) return null;
  // Banner ONLY shows when there is NO active subscription.
  if (status?.has_active_subscription) return null;

  const handlePay = async () => {
    try {
      setPaying(true);
      const r = await axios.post(`${API_BASE}/dealer-subscription/create-checkout-session`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.data?.url) window.location.assign(r.data.url);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[dealer-fee-banner] checkout failed:', err);
    } finally {
      setPaying(false);
    }
  };

  return (
    <div
      className="sticky top-0 z-[9999] w-full bg-amber-700 text-white shadow-lg"
      data-testid="global-dealer-fee-banner"
      role="alert"
    >
      <div className="mx-auto max-w-7xl px-3 sm:px-4 py-2.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
        <div className="flex items-start sm:items-center gap-2 min-w-0">
          <Lock className="h-5 w-5 flex-shrink-0 mt-0.5 sm:mt-0" aria-hidden />
          <div className="text-xs sm:text-sm leading-tight">
            <div className="font-bold">
              {isFr
                ? '🔒 Frais annuels de plateforme requis'
                : '🔒 Annual Platform Fee Required'}
            </div>
            <div className="opacity-95">
              {isFr
                ? "Vos frais de concessionnaire de 200 $ CAD/an (50 % de rabais = 100 $ CAD/an + taxes) n'ont pas été payés. Les fonctionnalités de listage sont BLOQUÉES."
                : 'Your Vehicle Dealer fee of $200 CAD/year (50% launch discount = $100 CAD/year + taxes) has not been paid. Listing capabilities are LOCKED.'}
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={handlePay}
          disabled={paying}
          className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-white text-amber-800 hover:bg-amber-50 px-4 py-2 text-xs sm:text-sm font-bold shadow-sm disabled:opacity-60"
          data-testid="global-dealer-fee-banner-pay-btn"
        >
          {paying
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <CreditCard className="h-4 w-4" />}
          {isFr ? 'Payer maintenant — 100$/an' : 'Pay Now — $100/yr'}
        </button>
      </div>
    </div>
  );
};

export default GlobalDealerFeeBanner;
