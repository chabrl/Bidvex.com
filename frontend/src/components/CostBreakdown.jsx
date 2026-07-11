/**
 * iter209 Step 4 — Cost Breakdown component (single source of truth UI)
 *
 * Renders the bilingual invoice-style breakdown for ANY auction type by
 * calling the backend `/api/fees/v2/preview` endpoint and selecting one
 * of FOUR display shapes based on `sellerAccountType`:
 *
 *   - individual       → hammer + buyer-tier BP + GST + QST + Stripe
 *   - partner          → hammer + partner BP + GST + QST + Stripe (or "Pay auctioneer directly" for cash/e-transfer)
 *   - vehicle_dealer   → hammer + 2.5% platform fee + GST + QST + Stripe
 *   - storage_facility → winning bid + $0 platform fee + "Pay facility directly" message
 *
 * Props:
 *   hammerPrice, auctionType, sellerAccountType, sellerUserId (optional),
 *   sellerTier, buyerTier, partnerBpRate, paymentMethod, cardType
 *
 * Use `compact={true}` for sidebars / cart row variants.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Loader2, Info } from 'lucide-react';
import API_BASE from '../config';

const fmt = (n, currency = 'CAD') =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency }).format(Number(n || 0));

const Row = ({ label, value, bold, mute, testid }) => (
  <div
    className={`flex items-center justify-between py-1 ${bold ? 'font-bold text-slate-900 dark:text-white border-t border-slate-200 dark:border-slate-700/40 mt-1 pt-2' : ''} ${mute ? 'text-xs text-slate-500' : 'text-sm text-slate-700 dark:text-slate-300'}`}
    data-testid={testid}
  >
    <span>{label}</span>
    <span className={`font-mono ${bold ? 'text-base' : ''}`}>{value}</span>
  </div>
);

export const CostBreakdown = ({
  hammerPrice,
  auctionType = 'marketplace',
  sellerAccountType = 'individual',
  sellerUserId,
  sellerTier,
  buyerTier = 'standard',
  partnerBpRate,
  paymentMethod = 'stripe',
  cardType = 'domestic',
  currency = 'CAD',
  compact = false,
  className = '',
  // iter343 BUG-6 — lot quantity semantics. BidVex bid model:
  //   • default: the bid is a PER-LOT TOTAL (covers all N items)
  //   • multiplyByQuantity=true (listing.multiply_hammer_by_quantity):
  //     the bid is PER ITEM → effective hammer = bid × quantity
  quantity = 1,
  multiplyByQuantity = false,
}) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [fee, setFee] = useState(null);
  const [loading, setLoading] = useState(true);

  const qty = Math.max(1, parseInt(quantity, 10) || 1);
  const perItem = multiplyByQuantity && qty > 1;
  const effectiveHammer = perItem ? hammerPrice * qty : hammerPrice;

  useEffect(() => {
    let alive = true;
    if (!effectiveHammer || effectiveHammer <= 0) { setFee(null); setLoading(false); return; }
    setLoading(true);
    const params = {
      hammer_price: effectiveHammer,
      auction_type: auctionType,
      seller_account_type: sellerAccountType,
      buyer_tier: buyerTier,
      payment_method: paymentMethod,
      card_type: cardType,
    };
    if (sellerTier) params.seller_tier = sellerTier;
    if (sellerUserId) params.seller_user_id = sellerUserId;
    if (partnerBpRate !== undefined && partnerBpRate !== null) params.partner_bp_rate = partnerBpRate;
    axios.get(`${API_BASE}/fees/v2/preview`, { params })
      .then(r => { if (alive) setFee(r.data); })
      .catch(() => { if (alive) setFee(null); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [effectiveHammer, auctionType, sellerAccountType, sellerUserId, sellerTier, buyerTier, partnerBpRate, paymentMethod, cardType]);

  if (loading || !fee) {
    return (
      <div className={`rounded-lg border border-slate-200 dark:border-slate-700/40 bg-slate-50 dark:bg-slate-900/40 p-3 text-xs text-slate-500 flex items-center gap-2 ${className}`} data-testid="cost-breakdown-loading">
        <Loader2 className="w-3 h-3 animate-spin" /> {isFr ? 'Calcul…' : 'Calculating…'}
      </div>
    );
  }

  const wrapperCls = `rounded-lg border border-slate-200 dark:border-slate-700/40 bg-white dark:bg-slate-900/40 ${compact ? 'px-3 py-2' : 'p-4'} ${className}`;
  const accountKind = sellerAccountType;

  // ── Storage facility — iter211 P0: buyer ALWAYS pays only hammer ──
  //  • cash / e-transfer → buyer pays facility directly (no BidVex flow)
  //  • stripe            → buyer pays hammer via Stripe (no fees, no BP)
  if (accountKind === 'storage_facility') {
    const isStripe = fee.charge_buyer_via_stripe === true;
    return (
      <div className={wrapperCls} data-testid="cost-breakdown-storage">
        <Row label={isFr ? 'Enchère gagnante' : 'Winning Bid'} value={fmt(fee.hammer_price, currency)} testid="cb-hammer" />
        <Row label={isFr ? 'Frais de plateforme BidVex' : 'BidVex Platform Fee'} value="$0.00" mute testid="cb-platform-zero" />
        <Row
          label={isStripe
            ? (isFr ? 'Total à payer' : 'Total You Pay')
            : (isFr ? "Vous payez l'établissement" : 'You Pay the Facility')}
          value={fmt(fee.hammer_price, currency)}
          bold
          testid="cb-total-storage"
        />
        <div className="mt-2 text-[11px] text-emerald-700 dark:text-emerald-400 flex items-start gap-1.5" data-testid="cb-storage-msg">
          <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>
            {isStripe ? (
              isFr
                ? "💡 L'établissement absorbe les frais de plateforme. Vous payez uniquement le montant de l'enchère."
                : '💡 The facility absorbs the platform fee. You pay only the winning bid amount.'
            ) : (
              isFr
                ? "💡 Le paiement est effectué directement à l'établissement de stockage (espèces ou virement Interac). Aucun frais BidVex n'est facturé aux acheteurs."
                : '💡 Payment is made directly to the storage facility (cash or Interac e-Transfer). No BidVex fees charged to buyers on this auction.'
            )}
          </span>
        </div>
      </div>
    );
  }

  const showStripe = fee.charge_buyer_via_stripe;
  // iter283-vehicle-bp-zero — Defence-in-depth: for vehicle context
  // (where `seller_account_type === 'vehicle_dealer'` and the backend
  // routes through the VEHICLE_DEALER_BUYER_RATE branch), the value
  // returned in `fee.buyer_premium` is the 2.5% PLATFORM FEE, not a
  // buyer premium. The label below already renders it as
  // "Platform Fee" so we keep the value, but we surface a stable
  // `buyer_premium_rate` of 2.5% via the same field so the
  // `(2.5%)` rate suffix remains accurate.
  //
  // Vehicles also have NO buyer-tier-based premium (Standard 5% /
  // Premium 3.5% / VIP Elite 3%) — that pricing matrix only applies
  // to the `individual` seller route. The vehicle_dealer route in
  // `services/fee_calculator.py` ALREADY sets the rate to the
  // canonical 2.5% regardless of tier; this is just a clarifying
  // pin so future agents don't accidentally inject a tier-based
  // override here.
  const buyerPremium = fee.buyer_premium;
  const buyerPremiumRate = fee.buyer_premium_rate || 0;
  const labelFee = accountKind === 'vehicle_dealer'
    ? (isFr ? 'Frais de plateforme' : 'Platform Fee')
    : (isFr ? "Prime de l'acheteur" : "Buyer's Premium");
  const ratePct = (buyerPremiumRate * 100).toFixed(2).replace(/\.?0+$/, '');

  return (
    <div className={wrapperCls} data-testid={`cost-breakdown-${accountKind}`}>
      {/* iter343 BUG-6 — quantity is always shown prominently for multi-item lots */}
      {qty > 1 && (
        <Row
          label={isFr ? 'Quantité' : 'Quantity'}
          value={isFr ? `${qty} articles` : `${qty} items`}
          testid="cb-quantity"
        />
      )}
      {perItem && (
        <Row
          label={isFr ? 'Prix par article' : 'Price per item'}
          value={fmt(hammerPrice, currency)}
          testid="cb-price-per-item"
        />
      )}
      <Row
        label={perItem
          ? (isFr ? `Prix au marteau (${qty} × unité)` : `Hammer Price (${qty} × unit)`)
          : qty > 1
            ? (isFr ? `Prix au marteau (total pour ${qty} articles)` : `Hammer Price (total for ${qty} items)`)
            : (isFr ? 'Prix au marteau' : 'Hammer Price')}
        value={fmt(fee.hammer_price, currency)}
        testid="cb-hammer"
      />
      {/* iter283-vehicle-bp-zero — Hide the fee row entirely when 0
          (e.g. storage_facility cash route). A zero-value row is
          misleading. */}
      {buyerPremium > 0 && (
        <Row
          label={`${labelFee} (${ratePct}%)`}
          value={`+${fmt(buyerPremium, currency)}`}
          testid="cb-buyer-premium"
        />
      )}
      <Row label={isFr ? 'TPS (5 %)' : 'GST (5%)'} value={`+${fmt(fee.buyer_gst, currency)}`} testid="cb-gst" />
      <Row label={isFr ? 'TVQ (9,975 %)' : 'QST (9.975%)'} value={`+${fmt(fee.buyer_qst, currency)}`} testid="cb-qst" />
      {showStripe ? (
        <Row label={isFr ? 'Traitement du paiement' : 'Payment Processing'} value={`+${fmt(fee.buyer_stripe_fee, currency)}`} testid="cb-stripe-fee" />
      ) : (
        <div className="mt-1 text-[11px] text-slate-600 dark:text-slate-400 flex items-start gap-1.5" data-testid="cb-cash-msg">
          <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>
            {isFr
              ? "Méthode de paiement : espèces / virement — payez le commissaire-priseur directement."
              : 'Payment method: Cash / E-Transfer — Pay the auctioneer directly.'}
          </span>
        </div>
      )}
      <Row
        label={isFr ? 'Total facturé' : 'Total Charged'}
        value={showStripe ? fmt(fee.buyer_total_charged, currency) : fmt(fee.hammer_price + buyerPremium + (fee.buyer_taxes || 0), currency)}
        bold
        testid="cb-total"
      />
    </div>
  );
};

export default CostBreakdown;
