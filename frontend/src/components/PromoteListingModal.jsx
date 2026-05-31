/**
 * iter239 Mission 5 — Promote Listing Modal
 *
 * Seller-facing dialog that posts to `POST /api/listings/{id}/promote` and
 * activates featured/promoted status across the selected sections. Phase 1
 * is FREE (no Stripe charge — backend simply flips the promotion fields);
 * Phase 2 will add Stripe Checkout per `promotion_tier`.
 */
import React, { useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Sparkles, Loader2 } from 'lucide-react';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';

const ALL_SECTIONS = [
  { id: 'marketplace', label_en: 'Marketplace', label_fr: 'Marketplace' },
  { id: 'lots',        label_en: 'Lots Auction', label_fr: 'Enchères par lots' },
  { id: 'storage',     label_en: 'Storage Auctions', label_fr: "Entreposage" },
  { id: 'vehicles',    label_en: 'Vehicle Auctions', label_fr: 'Véhicules' },
  { id: 'homepage',    label_en: 'Homepage', label_fr: "Page d'accueil" },
];

// iter241 Mission 1 — Pricing aligned with backend `PROMOTION_TIERS` in
// services/pricing_config.py. The UI `tier` field maps 1:1 to the backend
// `boost_tier` value sent in the Stripe checkout request body.
const TIERS = [
  { id: 'basic',    label_en: 'Basic',     label_fr: 'Basique',     price: '$9.99',  days: 7,  blurb_en: 'Featured badge + top of category',                            blurb_fr: "Badge + tête de catégorie" },
  { id: 'standard', label_en: 'Featured',  label_fr: 'En vedette',  price: '$24.99', days: 14, blurb_en: 'Featured badge + top + homepage',                             blurb_fr: 'Badge + tête + page d’accueil' },
  { id: 'premium',  label_en: 'Premium',   label_fr: 'Premium',     price: '$49.99', days: 30, blurb_en: 'Featured + top + homepage + email blast',                     blurb_fr: 'Badge + tête + page d’accueil + courriel' },
];

const PromoteListingModal = ({ open, onOpenChange, listing, onSuccess }) => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const isFr = (i18n.language || 'en').startsWith('fr');
  const t = (en, fr) => (isFr ? fr : en);

  const [sections, setSections] = useState(['marketplace']);
  const [tier, setTier] = useState('standard');
  const [submitting, setSubmitting] = useState(false);
  // iter242 Mission 2 — Coupon code support + discount preview state.
  const [couponCode, setCouponCode] = useState('');
  const [discount, setDiscount] = useState(null); // {applies, is_full_waiver, ...}
  const [previewing, setPreviewing] = useState(false);

  // Duration is now fixed per-tier (Stripe pricing tied to duration).
  const activeTier = TIERS.find((x) => x.id === tier) || TIERS[1];
  const duration = activeTier.days;

  const toggleSection = (id) => {
    setSections((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  // iter242 Mission 2 — Preview discount BEFORE redirecting to Stripe.
  // The backend evaluates the coupon + active platform promotions and
  // returns whether the listing-promotion fee will be waived (is_full_waiver).
  const previewDiscount = async () => {
    if (!listing?.id) return;
    setPreviewing(true);
    setDiscount(null);
    try {
      const basePrice = parseFloat(activeTier.price.replace(/[^0-9.]/g, '')) || 0;
      const params = new URLSearchParams({
        transaction_type: 'listing_promotion',
        base_amount_cad: String(basePrice),
        listing_type: (listing.listing_type || 'marketplace'),
      });
      if (couponCode.trim()) params.set('coupon_code', couponCode.trim().toUpperCase());
      const res = await axios.get(
        `${API_BASE}/promotions/preview-discount?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setDiscount(res.data);
      if (res.data?.is_full_waiver) {
        toast.success(t('Coupon validated! This promotion will be FREE.', 'Coupon validé ! Cette promotion sera GRATUITE.'));
      } else if (res.data?.applies) {
        toast.success(t(`Coupon validated — ${res.data.discount_percent}% off.`, `Coupon validé — ${res.data.discount_percent}% de réduction.`));
      } else {
        toast.message(t('No promotion applies to this transaction.', 'Aucune promotion applicable.'));
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || 'Preview failed';
      toast.error(typeof msg === 'string' ? msg : 'Preview failed');
    } finally {
      setPreviewing(false);
    }
  };

  const handlePromote = async () => {
    if (!listing?.id) return;
    if (sections.length === 0) {
      toast.error(t('Select at least one section', 'Sélectionnez au moins une section'));
      return;
    }
    setSubmitting(true);
    try {
      // iter241 Mission 1 — Route through Stripe Checkout. The backend
      // creates a Checkout Session and returns a session URL; we redirect
      // the seller to Stripe. On webhook completion the listing flips to
      // promoted automatically (`routes/webhooks._handle_listing_promotion_paid`).
      // The listing's primary listing_type drives the Stripe product label.
      const lt = (listing.listing_type || '').toLowerCase();
      const backend_lt =
        lt === 'lot_auction' || lt === 'multi_item_listing' ? 'lots' :
        lt === 'storage_locker' || lt === 'storage_auction' ? 'storage' :
        lt === 'vehicle' || lt === 'vehicle_auction' ? 'vehicle' :
        'marketplace';
      const res = await axios.post(
        `${API_BASE}/promote-listing`,
        {
          listing_id: listing.id,
          boost_tier: tier,
          listing_type: backend_lt,
          return_url: `${window.location.origin}/seller/dashboard?promo_session=1`,
          // Sections is recorded in metadata so the webhook can mirror it
          // onto the listing once the payment clears.
          sections,
          // iter242 Mission 2 — Forward the coupon so the backend can match
          // it against admin promotions and bypass Stripe when applicable.
          coupon_code: couponCode.trim().toUpperCase() || undefined,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      // iter242 Mission 2 — If the backend returned a "waived" flag, the
      // listing was promoted in-place at $0.00 and Stripe was bypassed.
      if (res?.data?.waived === true) {
        toast.success(
          t(
            `🎉 Promotion activated for FREE! Saved $${res.data.saved_amount_cad?.toFixed?.(2) || '0.00'}.`,
            `🎉 Promotion activée GRATUITEMENT ! Économie de ${res.data.saved_amount_cad?.toFixed?.(2) || '0.00'} $.`
          )
        );
        onSuccess?.(res.data);
        onOpenChange(false);
        return;
      }
      // Standard Stripe redirect.
      const checkoutUrl = res?.data?.url || res?.data?.checkout_url;
      if (!checkoutUrl) throw new Error('Stripe checkout URL missing in response');
      // Open in same tab so Stripe → return_url redirects feel native.
      window.location.href = checkoutUrl;
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Failed to start checkout';
      toast.error(typeof msg === 'string' ? msg : 'Promotion checkout failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg" data-testid="promote-listing-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber-500" />
            {t('Promote this listing', 'Promouvoir cette annonce')}
          </DialogTitle>
          <DialogDescription>
            {t(
              'Boost visibility across the BidVex network. Powered by Stripe — your card will be charged at the listed price + applicable taxes.',
              'Augmentez la visibilité sur le réseau BidVex. Propulsé par Stripe — votre carte sera débitée du prix affiché + taxes applicables.'
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Tier picker */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              {t('Promotion tier', 'Forfait')}
            </label>
            <div className="grid grid-cols-3 gap-2">
              {TIERS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setTier(opt.id)}
                  className={`p-2 rounded-lg border text-left transition-all ${
                    tier === opt.id
                      ? 'border-amber-500 bg-amber-50 ring-2 ring-amber-200'
                      : 'border-slate-200 bg-white hover:border-amber-300'
                  }`}
                  data-testid={`promote-tier-${opt.id}`}
                >
                  <div className="text-sm font-bold text-slate-900">
                    {isFr ? opt.label_fr : opt.label_en}
                  </div>
                  <div className="text-[11px] mt-0.5 font-semibold text-amber-700">
                    {opt.price} · {opt.days}d
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    {isFr ? opt.blurb_fr : opt.blurb_en}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Sections */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              {t('Sections to feature on', 'Sections à mettre en avant')}
            </label>
            <div className="flex flex-wrap gap-2">
              {ALL_SECTIONS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => toggleSection(s.id)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold border-[1.5px] transition-all ${
                    sections.includes(s.id)
                      ? 'bg-[#2d6be4] text-white border-[#2d6be4]'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-blue-300'
                  }`}
                  data-testid={`promote-section-${s.id}`}
                >
                  {isFr ? s.label_fr : s.label_en}
                </button>
              ))}
            </div>
          </div>

          {/* iter241 Mission 1 — Duration is now fixed per-tier, no manual override. */}

          {/* iter242 Mission 2 — Coupon code field + zero-fee preview. */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              {t('Coupon code (optional)', 'Code promo (facultatif)')}
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                placeholder="BIDVEX-XXXXXX"
                className="flex-1 px-3 py-2 border-[1.5px] border-slate-200 rounded-md text-sm uppercase font-mono"
                data-testid="promote-coupon-input"
              />
              <button
                type="button"
                onClick={previewDiscount}
                disabled={previewing}
                className="px-3 py-2 rounded-md border-[1.5px] border-slate-200 text-xs font-semibold hover:border-amber-400"
                data-testid="promote-preview-coupon-btn"
              >
                {previewing ? t('Checking…', 'Vérification…') : t('Apply', 'Appliquer')}
              </button>
            </div>
            {discount?.applies && (
              <div
                className={`mt-2 p-2 rounded-md text-xs ${discount.is_full_waiver
                  ? 'bg-emerald-50 border border-emerald-200 text-emerald-900'
                  : 'bg-blue-50 border border-blue-200 text-blue-900'}`}
                data-testid="promote-discount-preview"
              >
                {discount.is_full_waiver
                  ? t(
                      '✅ Full waiver applied — this promotion will be activated for FREE.',
                      '✅ Exonération complète — cette promotion sera activée GRATUITEMENT.'
                    )
                  : t(
                      `Coupon applies — ${discount.discount_percent}% off ($${discount.discount_amount?.toFixed?.(2)}).`,
                      `Coupon appliqué — ${discount.discount_percent}% de réduction (${discount.discount_amount?.toFixed?.(2)} $).`
                    )}
              </div>
            )}
          </div>

          {/* Summary */}
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 text-xs text-blue-900" data-testid="promote-summary">
            <p>
              <strong>{listing?.title || t('This listing', 'Cette annonce')}</strong>{' '}
              {t('will be promoted as', 'sera promu en tant que')}{' '}
              <strong>{activeTier[isFr ? 'label_fr' : 'label_en']}</strong>{' '}
              {t('for', 'pendant')} <strong>{duration}d</strong> {t('across', 'sur')}{' '}
              <strong>{sections.length}</strong> {t('section(s)', 'section(s)')}{' '}
              {t('— total', '— total')} <strong>{activeTier.price} CAD</strong>{' '}
              <span className="text-blue-700">({t('plus tax + Stripe fee', 'plus taxes + frais Stripe')})</span>.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting} data-testid="promote-cancel-btn">
            {t('Cancel', 'Annuler')}
          </Button>
          <Button
            onClick={handlePromote}
            disabled={submitting || sections.length === 0}
            className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white border-0"
            data-testid="promote-confirm-btn"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {discount?.is_full_waiver
                  ? t('Activating…', 'Activation…')
                  : t('Redirecting to Stripe…', 'Redirection vers Stripe…')}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                {discount?.is_full_waiver
                  ? t('Activate FREE promotion', 'Activer la promotion GRATUITE')
                  : t('Pay with Stripe', 'Payer avec Stripe')}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PromoteListingModal;
