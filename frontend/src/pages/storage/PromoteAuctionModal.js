/**
 * PromoteAuctionModal — iter193 (full i18n migration)
 * ====================================================
 * Facility-side modal for purchasing a promotion tier (Basic / Featured / Premium)
 * for one of their active storage auctions.
 *
 * Strict single-language rendering: tier names + features come from backend in both
 * EN and FR; we render only the active language based on i18n.language.
 */
import API_BASE from '../../config';
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { Loader2, Sparkles, Rocket, Crown, CheckCircle2, CreditCard } from 'lucide-react';

const API = API_BASE;
const stripePromise = loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY);

const TIER_META = {
  basic:    { icon: Sparkles, color: 'border-blue-300 bg-blue-50 dark:bg-blue-950/30 text-blue-800 dark:text-blue-200' },
  featured: { icon: Rocket,   color: 'border-purple-300 bg-purple-50 dark:bg-purple-950/30 text-purple-800 dark:text-purple-200' },
  premium:  { icon: Crown,    color: 'border-amber-300 bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-200' },
};

// ───────────────────────────────────────
// Inner payment form (needs Elements context)
// ───────────────────────────────────────
const PromotionPaymentForm = ({ auctionId, tierKey, spec, onSuccess, onCancel }) => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  const stripe = useStripe();
  const elements = useElements();
  const { token } = useAuth();
  const [processing, setProcessing] = useState(false);

  const tierName = isFr ? spec.name_fr : spec.name_en;
  const priceFmt = spec.price_cad.toFixed(2);

  const handlePay = async () => {
    if (!stripe || !elements) return;
    setProcessing(true);
    try {
      const { data } = await axios.post(
        `${API}/storage-auctions/${auctionId}/promote`,
        { tier: tierKey },
        { headers: { Authorization: `Bearer ${token}` } },
      );

      const { client_secret, payment_intent_id } = data;

      const card = elements.getElement(CardElement);
      const result = await stripe.confirmCardPayment(client_secret, {
        payment_method: { card },
      });

      if (result.error) {
        toast.error(t('storage.promoteModal.paymentFailedFmt', { message: result.error.message }));
        setProcessing(false);
        return;
      }

      await axios.post(
        `${API}/storage-auctions/${auctionId}/promote/confirm`,
        { payment_intent_id },
        { headers: { Authorization: `Bearer ${token}` } },
      );

      toast.success(t('storage.promoteModal.promotionActivated'));
      onSuccess?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : (detail || t('storage.promoteModal.failed'));
      toast.error(msg);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div data-testid="promotion-payment-form" className="space-y-4">
      <div className="rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 p-4">
        <p className="text-xs uppercase tracking-wider text-muted-foreground">{t('storage.promoteModal.youArePaying')}</p>
        <p className="text-3xl font-black mt-1">
          ${priceFmt} CAD
          <span className="text-xs font-normal text-muted-foreground ml-2">
            {t('storage.promoteModal.perDays', { days: spec.duration_days })}
          </span>
        </p>
        <p className="text-sm font-semibold mt-1">{tierName}</p>
      </div>

      <div className="rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 p-3">
        <label className="text-xs font-medium mb-2 block flex items-center gap-1">
          <CreditCard className="h-3 w-3" />
          {t('storage.promoteModal.cardDetails')}
        </label>
        <CardElement
          options={{
            style: {
              base: { fontSize: '15px', color: '#1e293b', '::placeholder': { color: '#94a3b8' } },
              invalid: { color: '#dc2626' },
            },
          }}
        />
      </div>

      <p className="text-[10px] text-muted-foreground">
        {t('storage.promoteModal.oneTimePaymentInfo')}
      </p>

      <DialogFooter className="gap-2">
        <Button variant="outline" onClick={onCancel} disabled={processing} data-testid="promotion-payment-cancel">
          {t('storage.promoteModal.cancelBtn')}
        </Button>
        <Button
          onClick={handlePay}
          disabled={processing || !stripe}
          className="bg-blue-600 hover:bg-blue-700 text-white"
          data-testid="promotion-payment-submit"
        >
          {processing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <CheckCircle2 className="h-4 w-4 mr-1" />}
          {t('storage.promoteModal.payBtnFmt', { amount: priceFmt })}
        </Button>
      </DialogFooter>
    </div>
  );
};

// ───────────────────────────────────────
// Main modal
// ───────────────────────────────────────
const PromoteAuctionModal = ({ auction, open, onOpenChange, onSuccess }) => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  const [tiers, setTiers] = useState({});
  const [selectedTier, setSelectedTier] = useState(null);
  const [loadingTiers, setLoadingTiers] = useState(false);

  useEffect(() => {
    if (!open) {
      setSelectedTier(null);
      return;
    }
    setLoadingTiers(true);
    axios.get(`${API}/storage-promotion-tiers`)
      .then(r => setTiers(r.data?.tiers || {}))
      .catch(() => toast.error(t('storage.promoteModal.failedToLoadTiers')))
      .finally(() => setLoadingTiers(false));
  }, [open, t]);

  if (!auction) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="promote-auction-modal">
        <DialogHeader>
          <DialogTitle className="text-xl">
            {t('storage.promoteModal.modalTitleFmt', { unit: auction.unit_number })}
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            {t('storage.promoteModal.modalSubtitle')}
          </p>
        </DialogHeader>

        {loadingTiers && (
          <div className="py-10 flex justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>
        )}

        {/* TIER SELECTION */}
        {!loadingTiers && !selectedTier && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="promotion-tier-grid">
            {Object.entries(tiers).map(([key, spec]) => {
              const meta = TIER_META[key] || TIER_META.basic;
              const Icon = meta.icon;
              const tierName = isFr ? spec.name_fr : spec.name_en;
              const features = isFr ? spec.features_fr : spec.features_en;
              return (
                <Card
                  key={key}
                  className={`p-4 cursor-pointer hover:scale-[1.02] transition-transform border-2 ${meta.color}`}
                  onClick={() => setSelectedTier(key)}
                  data-testid={`promotion-tier-${key}`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className="h-5 w-5" />
                    <h3 className="font-bold text-lg">{tierName}</h3>
                  </div>
                  <div className="text-3xl font-black mb-1">${spec.price_cad.toFixed(2)}</div>
                  <p className="text-xs opacity-80 mb-3">
                    {t('storage.promoteModal.durationDaysFmt', { days: spec.duration_days })}
                  </p>
                  <ul className="space-y-1">
                    {features.map((f, i) => (
                      <li key={i} className="text-xs flex items-start gap-1">
                        <CheckCircle2 className="h-3 w-3 mt-0.5 shrink-0" /> {f}
                      </li>
                    ))}
                  </ul>
                  <Button
                    className="w-full mt-3 bg-slate-900 hover:bg-slate-800 text-white"
                    data-testid={`promotion-tier-select-${key}`}
                  >
                    {t('storage.promoteModal.selectBtn')}
                  </Button>
                </Card>
              );
            })}
          </div>
        )}

        {/* PAYMENT FORM */}
        {selectedTier && tiers[selectedTier] && (
          <Elements stripe={stripePromise}>
            <PromotionPaymentForm
              auctionId={auction.id}
              tierKey={selectedTier}
              spec={tiers[selectedTier]}
              onSuccess={() => {
                onOpenChange?.(false);
                onSuccess?.();
              }}
              onCancel={() => setSelectedTier(null)}
            />
          </Elements>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default PromoteAuctionModal;
