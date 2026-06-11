/**
 * StripeConnectBanner — iter302 Directive 2.
 *
 * Seller dashboard banner: when the seller has no ready Stripe Connect
 * account, prompts onboarding so post-auction payouts land instantly
 * instead of going through the manual 14-business-day queue.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Zap, CheckCircle2, Loader2 } from 'lucide-react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { useAuth } from '../contexts/AuthContext';
import API_BASE from '../config';

const StripeConnectBanner = () => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const fr = (i18n.language || 'en').startsWith('fr');
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  const fetchStatus = useCallback(async () => {
    if (!token) return;
    try {
      const r = await axios.get(`${API_BASE}/settlement/connect/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStatus(r.data);
    } catch {
      setStatus(null);
    }
  }, [token]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('stripe') === 'connected') {
      toast.success(fr ? 'Compte Stripe connecté ! Vérification en cours…' : 'Stripe account connected! Verifying…');
      window.history.replaceState({}, '', window.location.pathname);
    }
    fetchStatus();
  }, [fetchStatus]);

  const startOnboarding = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API_BASE}/settlement/connect/onboard`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.data?.onboarding_url) {
        window.location.href = r.data.onboarding_url;
      } else {
        toast.error(fr ? "Impossible de démarrer l'inscription Stripe" : 'Could not start Stripe onboarding');
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? "Échec de l'inscription Stripe" : 'Stripe onboarding failed'));
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;

  if (status.payouts_enabled) {
    return (
      <div
        className="flex items-center gap-2 text-sm px-4 py-2.5 rounded-lg border border-emerald-200 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-300"
        data-testid="stripe-connect-active"
      >
        <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
        {fr
          ? 'Versements instantanés actifs — vos gains sont transférés automatiquement via Stripe.'
          : 'Instant payouts active — your earnings are transferred automatically via Stripe.'}
      </div>
    );
  }

  return (
    <Card className="border-2 border-indigo-300/60 bg-gradient-to-r from-indigo-50 to-cyan-50 dark:from-indigo-950/40 dark:to-cyan-950/40" data-testid="stripe-connect-banner">
      <CardContent className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
        <div className="flex items-start gap-3 flex-1">
          <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/50 flex-shrink-0">
            <Zap className="h-5 w-5 text-indigo-600" />
          </div>
          <div>
            <p className="font-semibold text-sm sm:text-base">
              {fr ? 'Recevez vos versements instantanément' : 'Get paid instantly'}
            </p>
            <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
              {fr
                ? 'Connectez votre compte Stripe pour recevoir vos gains automatiquement dès le paiement de l\u2019acheteur. Sans Stripe, les versements manuels prennent jusqu\u2019à 14 jours ouvrables.'
                : 'Connect your Stripe account to receive earnings automatically the moment the buyer pays. Without Stripe, manual payouts take up to 14 business days.'}
            </p>
          </div>
        </div>
        <Button
          className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-700 text-white border-0 flex-shrink-0"
          onClick={startOnboarding}
          disabled={busy}
          data-testid="stripe-connect-onboard-btn"
        >
          {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Zap className="h-4 w-4 mr-2" />}
          {status.connected
            ? (fr ? 'Terminer l\u2019inscription Stripe' : 'Finish Stripe setup')
            : (fr ? 'Configurer les versements' : 'Set up payouts')}
        </Button>
      </CardContent>
    </Card>
  );
};

export default StripeConnectBanner;
