import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
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
    color: 'from-blue-500 to-blue-600',
    border: 'border-blue-200',
    bg: 'bg-blue-50',
    badge: 'bg-blue-100 text-blue-700',
  },
  {
    key: 'standard',
    icon: Star,
    price: 24.99,
    color: 'from-violet-500 to-violet-600',
    border: 'border-violet-200',
    bg: 'bg-violet-50',
    badge: 'bg-violet-100 text-violet-700',
    popular: true,
  },
  {
    key: 'premium',
    icon: Crown,
    price: 49.99,
    color: 'from-amber-500 to-amber-600',
    border: 'border-amber-200',
    bg: 'bg-amber-50',
    badge: 'bg-amber-100 text-amber-700',
  },
];

const ListingPromotionModal = ({ listingId, listingTitle, onClose, isOpen }) => {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [purchasing, setPurchasing] = useState(null);
  const isFr = i18n.language === 'fr';

  if (!isOpen) return null;

  const tierLabels = {
    basic: { en: 'Basic Boost', fr: 'Promotion de Base', days: 7, features: ['Homepage highlight', 'Search priority'] },
    standard: { en: 'Standard Boost', fr: 'Promotion Standard', days: 14, features: ['Homepage highlight', 'Search priority', 'Category banner'] },
    premium: { en: 'Premium Boost', fr: 'Promotion Premium', days: 30, features: ['Homepage highlight', 'Search priority', 'Category banner', 'Email blast', 'Social share'] },
  };

  const handlePurchase = async (tier) => {
    setPurchasing(tier);
    try {
      const res = await axios.post(
        `${API}/payments/promote-listing`,
        {
          listing_id: listingId,
          tier,
          return_url: window.location.href,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to start checkout';
      alert(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setPurchasing(null);
    }
  };

  const formatCAD = (v) =>
    new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA', { style: 'currency', currency: 'CAD' }).format(v);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" data-testid="promotion-modal">
      <Card className="w-full max-w-2xl bg-white dark:bg-slate-900 shadow-2xl animate-in fade-in zoom-in-95 max-h-[90vh] overflow-y-auto">
        <CardHeader className="pb-3 border-b">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">{isFr ? 'Promouvoir votre annonce' : 'Promote Your Listing'}</CardTitle>
              <p className="text-sm text-muted-foreground mt-1 truncate max-w-[300px]">{listingTitle}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={onClose} data-testid="close-promotion-modal">
              &times;
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {PROMO_TIERS.map((tier) => {
              const info = tierLabels[tier.key];
              const Icon = tier.icon;
              const tax = tier.price * 0.14975;
              const total = tier.price + tax;
              return (
                <div
                  key={tier.key}
                  className={`relative rounded-xl border-2 ${tier.border} ${tier.bg} dark:bg-slate-800 p-4 flex flex-col`}
                  data-testid={`promo-tier-${tier.key}`}
                >
                  {tier.popular && (
                    <Badge className="absolute -top-2.5 left-1/2 -translate-x-1/2 bg-violet-600 text-white text-[10px] px-2">
                      {isFr ? 'POPULAIRE' : 'POPULAR'}
                    </Badge>
                  )}
                  <div className="flex items-center gap-2 mb-3">
                    <div className={`h-8 w-8 rounded-lg bg-gradient-to-br ${tier.color} flex items-center justify-center`}>
                      <Icon className="h-4 w-4 text-white" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-sm">{isFr ? info.fr : info.en}</h3>
                      <p className="text-xs text-muted-foreground">{info.days} {isFr ? 'jours' : 'days'}</p>
                    </div>
                  </div>

                  <div className="mb-3">
                    <span className="text-2xl font-bold">{formatCAD(tier.price)}</span>
                    <span className="text-xs text-muted-foreground ml-1">+ {isFr ? 'taxes' : 'tax'}</span>
                  </div>

                  <ul className="space-y-1.5 mb-4 flex-1">
                    {info.features.map((f, i) => (
                      <li key={i} className="flex items-center gap-1.5 text-xs">
                        <Check className="h-3 w-3 text-emerald-500 shrink-0" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>

                  <div className="text-[10px] text-muted-foreground mb-2 space-y-0.5">
                    <div className="flex justify-between"><span>GST (5%)</span><span>{formatCAD(tier.price * 0.05)}</span></div>
                    <div className="flex justify-between"><span>QST (9.975%)</span><span>{formatCAD(tier.price * 0.09975)}</span></div>
                    <div className="flex justify-between font-medium border-t pt-0.5"><span>Total</span><span>{formatCAD(total)}</span></div>
                  </div>

                  <Button
                    onClick={() => handlePurchase(tier.key)}
                    disabled={purchasing !== null}
                    className={`w-full bg-gradient-to-r ${tier.color} text-white text-sm`}
                    data-testid={`buy-promo-${tier.key}`}
                  >
                    {purchasing === tier.key ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>{isFr ? 'Acheter' : 'Purchase'}</>
                    )}
                  </Button>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
            <TrendingUp className="h-4 w-4 shrink-0" />
            <span>
              {isFr
                ? 'Les annonces promues reçoivent en moyenne 3x plus de vues et 2x plus d\'enchères.'
                : 'Promoted listings receive on average 3x more views and 2x more bids.'}
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ListingPromotionModal;
