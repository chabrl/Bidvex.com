import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import API_BASE from '../config';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Zap, Star, Crown, Loader2, Check, TrendingUp } from 'lucide-react';

const API = API_BASE;

const PROMO_TIERS = [
  {
    key: 'basic',
    icon: Zap,
    price: 9.99,
    duration_days: 7,
    color: 'from-blue-500 to-blue-600',
    border: 'border-blue-200',
    bg: 'bg-blue-50',
  },
  {
    key: 'standard',
    icon: Star,
    price: 24.99,
    duration_days: 14,
    color: 'from-purple-500 to-purple-600',
    border: 'border-purple-200',
    bg: 'bg-purple-50',
  },
  {
    key: 'premium',
    icon: Crown,
    price: 49.99,
    duration_days: 30,
    color: 'from-amber-500 to-amber-600',
    border: 'border-amber-200',
    bg: 'bg-amber-50',
  },
];

const FEATURES = {
  marketplace: {
    basic:    ['Homepage highlight', 'Search priority'],
    standard: ['Homepage highlight', 'Search priority', 'Category banner'],
    premium:  ['Homepage highlight', 'Search priority', 'Category banner', 'Email blast', 'Social share'],
  },
  lots: {
    basic:    ['Search priority', 'Homepage placement'],
    standard: ['Search priority', 'Homepage placement', 'Category banner', 'Featured badge'],
    premium:  ['Search priority', 'Homepage placement', 'Category banner', 'Featured badge', 'Email blast', 'Social share'],
  },
  storage: {
    basic:    ['Homepage highlight', 'Search priority'],
    standard: ['Homepage highlight', 'Search priority', 'Category banner on Storage page'],
    premium:  ['Homepage highlight', 'Search priority', 'Category banner on Storage page', 'Email blast to storage waitlist', 'Social share'],
  },
  partner: {
    basic:    ['Search priority', 'Homepage placement'],
    standard: ['Search priority', 'Homepage placement', 'Category banner', 'Featured badge'],
    premium:  ['Search priority', 'Homepage placement', 'Category banner', 'Featured badge', 'Email blast', 'Social share', 'Featured Partner badge'],
  },
};

const HEADER_EN = {
  marketplace: 'Promote Your Listing',
  lots: 'Promote Your Lot Auction',
  storage: 'Promote Your Storage Auction',
  partner: 'Promote Your Lot Auction',
};
const HEADER_FR = {
  marketplace: 'Promouvoir votre annonce',
  lots: 'Promouvoir votre vente aux enchères par lots',
  storage: 'Promouvoir votre enchère d\u2019entreposage',
  partner: 'Promouvoir votre vente aux enchères par lots',
};

/**
 * ListingPromotionModal
 * Works for all listing types: marketplace | lots | storage | partner
 *
 * Props:
 *  - listingId (required)
 *  - listingTitle
 *  - listingType: one of the four keys above (defaults to "marketplace")
 *  - onClose: () => void
 *  - onSuccess: optional callback before redirect
 */
const ListingPromotionModal = ({ listingId, listingTitle, listingType = 'marketplace', onClose, onSuccess }) => {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [selectedTier, setSelectedTier] = useState(null);
  const [loading, setLoading] = useState(false);

  const isFr = i18n.language === 'fr';

  // Live cost-breakdown preview that matches backend gross-up formula
  const preview = useMemo(() => {
    if (!selectedTier) return null;
    const tier = PROMO_TIERS.find((ti) => ti.key === selectedTier);
    if (!tier) return null;
    const base = tier.price;
    const gst = Math.round(base * 0.05 * 100) / 100;
    const qst = Math.round(base * 0.09975 * 100) / 100;
    const subtotal = Math.round((base + gst + qst) * 100) / 100;
    const stripe_fee = Math.round(((subtotal + 0.30) / (1 - 0.029) - subtotal) * 100) / 100;
    const grand = Math.round((subtotal + stripe_fee) * 100) / 100;
    return { base, gst, qst, subtotal, stripe_fee, grand, duration_days: tier.duration_days };
  }, [selectedTier]);

  const handlePurchase = async () => {
    if (!selectedTier) {
      toast.error(isFr ? 'Sélectionnez un niveau de promotion' : 'Please select a boost tier');
      return;
    }
    setLoading(true);
    try {
      const res = await axios.post(
        `${API}/payments/promote-listing`,
        {
          listing_id: listingId,
          boost_tier: selectedTier,
          listing_type: listingType,
          return_url: `${window.location.origin}/listing/${listingId}`,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (onSuccess) onSuccess(res.data);
      if (res.data?.checkout_url) {
        window.location.href = res.data.checkout_url;
        return;
      }
      toast.error(isFr ? 'Session de paiement introuvable' : 'Could not create payment session');
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Payment failed';
      toast.error(typeof detail === 'string' ? detail : 'Payment failed');
    } finally {
      setLoading(false);
    }
  };

  const headerLabel = (isFr ? HEADER_FR : HEADER_EN)[listingType] || HEADER_EN.marketplace;
  const featuresForType = FEATURES[listingType] || FEATURES.marketplace;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" data-testid="promote-listing-modal">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl max-w-4xl w-full max-h-[92vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2" data-testid="promote-listing-title">
              <TrendingUp className="w-6 h-6 text-amber-500" />
              {headerLabel}
            </h2>
            {listingTitle && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 truncate max-w-xl">{listingTitle}</p>
            )}
          </div>
          <button type="button" onClick={onClose} className="text-gray-500 hover:text-gray-900 dark:hover:text-white text-2xl leading-none" aria-label="Close">×</button>
        </div>

        <div className="p-6">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            {isFr
              ? 'Choisissez un niveau pour augmenter la visibilité et recevoir plus d\u2019enchères.'
              : 'Choose a boost tier to increase visibility and get more bids on your listing.'}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {PROMO_TIERS.map((tier) => {
              const Icon = tier.icon;
              const isSelected = selectedTier === tier.key;
              const feats = featuresForType[tier.key] || [];
              return (
                <Card
                  key={tier.key}
                  className={`cursor-pointer transition-all ${isSelected ? `border-2 ${tier.border} ${tier.bg} dark:bg-opacity-10` : 'border hover:border-gray-400'}`}
                  onClick={() => setSelectedTier(tier.key)}
                  data-testid={`tier-${tier.key}`}
                >
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <span className="flex items-center gap-2 capitalize">
                        <Icon className="w-5 h-5" />
                        {tier.key}
                      </span>
                      {isSelected && (
                        <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center">
                          <Check className="w-4 h-4 text-white" />
                        </div>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="mb-3">
                      <div className="text-3xl font-bold">${tier.price.toFixed(2)}</div>
                      <div className="text-xs text-gray-500">CAD (pre-tax)</div>
                      <Badge variant="secondary" className="mt-1">{tier.duration_days} days</Badge>
                    </div>
                    <ul className="space-y-1 text-sm">
                      {feats.map((f, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <Check className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {preview && (
            <div className="mt-6 p-4 rounded-lg bg-gray-50 dark:bg-gray-800 text-sm" data-testid="promotion-breakdown">
              <div className="flex justify-between py-1"><span>{isFr ? 'Prix de base' : 'Base price'}</span><span>${preview.base.toFixed(2)}</span></div>
              <div className="flex justify-between py-1"><span>{isFr ? 'TPS (5 %)' : 'GST (5%)'}</span><span>+${preview.gst.toFixed(2)}</span></div>
              <div className="flex justify-between py-1"><span>{isFr ? 'TVQ (9,975 %)' : 'QST (9.975%)'}</span><span>+${preview.qst.toFixed(2)}</span></div>
              <div className="flex justify-between py-1" data-testid="promo-stripe-fee-row">
                <span>
                  {isFr ? 'Frais de traitement (2,9 % + 0,30 $)' : 'Payment Processing (2.9% + $0.30)'}
                  <span className="ml-1" title={isFr
                    ? 'Frais de traitement Stripe — répercutés sans majoration.'
                    : 'Stripe card processing fee — passed through with no markup.'}>ℹ️</span>
                </span>
                <span>+${preview.stripe_fee.toFixed(2)}</span>
              </div>
              <div className="flex justify-between pt-2 mt-2 border-t font-bold">
                <span>{isFr ? 'Total facturé' : 'Total Charged'}</span>
                <span data-testid="promo-grand-total">${preview.grand.toFixed(2)} CAD</span>
              </div>
              <p className="text-[11px] text-gray-500 mt-2 italic">
                {isFr
                  ? 'Estimation — le montant exact sera confirmé à la caisse.'
                  : 'Estimate — final amount will be confirmed at checkout.'}
              </p>
            </div>
          )}

          <div className="flex gap-3 justify-end pt-6">
            <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
              {isFr ? 'Annuler' : 'Cancel'}
            </Button>
            <Button
              type="button"
              onClick={handlePurchase}
              disabled={!selectedTier || loading}
              data-testid="promote-purchase-btn"
              className="bg-gradient-to-r from-blue-600 to-purple-600 text-white"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {loading
                ? (isFr ? 'Traitement…' : 'Processing…')
                : (isFr ? 'Acheter' : `Purchase ${selectedTier ? selectedTier[0].toUpperCase() + selectedTier.slice(1) : ''} Boost`)}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ListingPromotionModal;
