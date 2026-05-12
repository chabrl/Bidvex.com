/**
 * iter209 Step 3 — Partner Payment Settings page.
 *
 * Located under Partner Dashboard. Shows:
 *   - Currently saved card (brand · •••• last4 · exp MM/YYYY) + Remove button
 *   - OR a "Add a card" card with Stripe PaymentElement that creates a SetupIntent
 *     and confirms it via stripe.confirmSetup()
 *
 * Why we need this: when a partner picks cash/e-transfer as the listing
 * payment method, BidVex auto-charges the 3% platform commission to this
 * saved card off-session via PaymentIntent.create(..., off_session=True).
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { CreditCard, Trash2, Loader2, ShieldCheck, AlertTriangle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import API_BASE from '../config';

const stripePromise = process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY
  ? loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY)
  : null;

const CardSetupForm = ({ onAdded, onCancel }) => {
  const stripe = useStripe();
  const elements = useElements();
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!stripe || !elements) return;
    setSubmitting(true);
    try {
      const result = await stripe.confirmSetup({
        elements,
        confirmParams: { return_url: window.location.href },
        redirect: 'if_required',
      });
      if (result.error) {
        toast.error(result.error.message);
        setSubmitting(false);
        return;
      }
      const pmId = result.setupIntent?.payment_method;
      if (!pmId) {
        toast.error(isFr ? "Aucune méthode de paiement reçue." : 'No payment method received from Stripe.');
        setSubmitting(false);
        return;
      }
      // Persist on backend
      const persistRes = await axios.post(
        `${API_BASE}/partner/saved-card/confirm`,
        { payment_method_id: pmId },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(isFr ? 'Carte enregistrée avec succès.' : 'Card saved successfully.');
      onAdded?.(persistRes.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail?.message || err?.message || 'Failed to save card');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="partner-card-setup-form">
      <PaymentElement options={{ layout: 'tabs' }} />
      <div className="flex gap-2 justify-end">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={submitting} data-testid="partner-card-cancel-btn">
            {isFr ? 'Annuler' : 'Cancel'}
          </Button>
        )}
        <Button
          type="submit"
          disabled={!stripe || submitting}
          data-testid="partner-card-submit-btn"
          className="bg-blue-600 hover:bg-blue-700 text-white"
        >
          {submitting ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> {isFr ? 'Enregistrement…' : 'Saving…'}</>
          ) : (
            <><ShieldCheck className="w-4 h-4 mr-2" /> {isFr ? 'Enregistrer la carte' : 'Save card'}</>
          )}
        </Button>
      </div>
    </form>
  );
};

const PartnerPaymentSettings = () => {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const [savedCard, setSavedCard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [clientSecret, setClientSecret] = useState(null);
  const [stripePublishableKey, setStripePublishableKey] = useState(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY || null);
  const [creating, setCreating] = useState(false);
  const [stripeLoaded, setStripeLoaded] = useState(stripePromise);

  const fetchCard = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/partner/saved-card`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSavedCard(r.data?.has_card ? r.data : null);
    } catch (e) {
      setSavedCard(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchCard(); }, [fetchCard]);

  const beginAddCard = async () => {
    setCreating(true);
    try {
      const r = await axios.post(`${API_BASE}/partner/setup-card`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setClientSecret(r.data.client_secret);
      // Backend hands us the publishable key if frontend env var is missing
      if (!stripePublishableKey && r.data.publishable_key) {
        setStripePublishableKey(r.data.publishable_key);
        setStripeLoaded(loadStripe(r.data.publishable_key));
      }
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg = (detail && typeof detail === 'object') ? (isFr ? detail.message_fr : detail.message_en) : (detail || (isFr ? 'Échec' : 'Failed'));
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  };

  const removeCard = async () => {
    if (!window.confirm(isFr ? 'Supprimer cette carte ?' : 'Remove this card?')) return;
    try {
      await axios.delete(`${API_BASE}/partner/saved-card`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSavedCard(null);
      toast.success(isFr ? 'Carte supprimée.' : 'Card removed.');
    } catch (e) {
      toast.error(isFr ? 'Échec de la suppression' : 'Failed to remove card');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-8" data-testid="partner-payment-settings-page">
      <div className="max-w-2xl mx-auto px-4">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
          {isFr ? 'Paramètres de paiement' : 'Payment Settings'}
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
          {isFr
            ? 'Enregistrez une carte pour pouvoir offrir le paiement en espèces ou par virement aux acheteurs. La commission de plateforme BidVex (3 %) sera prélevée automatiquement à la clôture de chaque enchère réglée hors plateforme.'
            : "Save a card to be able to offer cash or e-transfer payment to buyers. BidVex's 3% platform commission will be auto-charged when an off-platform auction closes."}
        </p>

        <Card className="border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CreditCard className="w-4 h-4" />
              {isFr ? 'Carte enregistrée' : 'Saved card'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-slate-500" data-testid="partner-card-loading">
                <Loader2 className="w-4 h-4 animate-spin" /> {isFr ? 'Chargement…' : 'Loading…'}
              </div>
            ) : savedCard ? (
              <div
                className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-lg border border-slate-200 dark:border-slate-700/40 px-4 py-3 bg-slate-50 dark:bg-slate-900/60"
                data-testid="partner-saved-card-row"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white capitalize" data-testid="partner-saved-card-brand">
                    {savedCard.brand || 'card'}
                  </p>
                  <p className="text-sm text-slate-600 dark:text-slate-300 font-mono" data-testid="partner-saved-card-last4">
                    •••• •••• •••• {savedCard.last4}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {isFr ? 'Expire' : 'Expires'} {String(savedCard.exp_month).padStart(2, '0')}/{savedCard.exp_year}
                  </p>
                </div>
                <Button variant="outline" onClick={removeCard} data-testid="partner-remove-card-btn">
                  <Trash2 className="w-4 h-4 mr-1.5" />
                  {isFr ? 'Supprimer' : 'Remove'}
                </Button>
              </div>
            ) : clientSecret ? (
              stripeLoaded ? (
                <Elements stripe={stripeLoaded} options={{ clientSecret, appearance: { theme: 'stripe' } }}>
                  <CardSetupForm
                    onAdded={() => { setClientSecret(null); fetchCard(); }}
                    onCancel={() => setClientSecret(null)}
                  />
                </Elements>
              ) : (
                <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  {isFr ? 'Chargement de Stripe…' : 'Loading Stripe…'}
                </div>
              )
            ) : (
              <div className="text-center py-4 space-y-3">
                <p className="text-sm text-slate-600 dark:text-slate-400" data-testid="partner-no-card-msg">
                  {isFr ? 'Aucune carte enregistrée.' : 'No card on file.'}
                </p>
                <Button
                  onClick={beginAddCard}
                  disabled={creating}
                  data-testid="partner-add-card-btn"
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {creating ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> {isFr ? 'Initialisation…' : 'Preparing…'}</>
                  ) : (
                    <><CreditCard className="w-4 h-4 mr-2" /> {isFr ? 'Ajouter une carte' : 'Add a card'}</>
                  )}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default PartnerPaymentSettings;
