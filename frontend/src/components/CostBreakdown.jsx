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
}) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [fee, setFee] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    if (!hammerPrice || hammerPrice <= 0) { setFee(null); setLoading(false); return; }
    setLoading(true);
    const params = {
      hammer_price: hammerPrice,
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
  }, [hammerPrice, auctionType, sellerAccountType, sellerUserId, sellerTier, buyerTier, partnerBpRate, paymentMethod, cardType]);

  if (loading || !fee) {
    return (
      <div className={`rounded-lg border border-slate-200 dark:border-slate-700/40 bg-slate-50 dark:bg-slate-900/40 p-3 text-xs text-slate-500 flex items-center gap-2 ${className}`} data-testid="cost-breakdown-loading">
        <Loader2 className="w-3 h-3 animate-spin" /> {isFr ? 'Calcul…' : 'Calculating…'}
      </div>
    );
  }

  const wrapperCls = `rounded-lg border border-slate-200 dark:border-slate-700/40 bg-white dark:bg-slate-900/40 ${compact ? 'px-3 py-2' : 'p-4'} ${className}`;
  const accountKind = sellerAccountType;

  // ── Storage facility — buyer pays facility directly, no BidVex Stripe ──
  if (accountKind === 'storage_facility') {
    return (
      <div className={wrapperCls} data-testid="cost-breakdown-storage">
        <Row label={isFr ? 'Enchère gagnante' : 'Winning Bid'} value={fmt(fee.hammer_price, currency)} testid="cb-hammer" />
        <Row label={isFr ? 'Frais de plateforme' : 'Platform Fee'} value="$0.00" mute testid="cb-platform-zero" />
        <Row
          label={isFr ? "Vous payez l'établissement" : 'You Pay Facility'}
          value={fmt(fee.hammer_price, currency)}
          bold
          testid="cb-total-storage"
        />
        <div className="mt-2 text-[11px] text-emerald-700 dark:text-emerald-400 flex items-start gap-1.5" data-testid="cb-pay-facility-msg">
          <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>
            {isFr
              ? "💡 Le paiement est effectué directement à l'établissement de stockage."
              : '💡 Payment is made directly to the storage facility.'}
          </span>
        </div>
      </div>
    );
  }

  const showStripe = fee.charge_buyer_via_stripe;
  const labelFee = accountKind === 'vehicle_dealer'
    ? (isFr ? 'Frais de plateforme' : 'Platform Fee')
    : (isFr ? "Prime de l'acheteur" : "Buyer's Premium");
  const ratePct = (fee.buyer_premium_rate * 100).toFixed(2).replace(/\.?0+$/, '');

  return (
    <div className={wrapperCls} data-testid={`cost-breakdown-${accountKind}`}>
      <Row label={isFr ? 'Prix au marteau' : 'Hammer Price'} value={fmt(fee.hammer_price, currency)} testid="cb-hammer" />
      <Row
        label={`${labelFee} (${ratePct}%)`}
        value={`+${fmt(fee.buyer_premium, currency)}`}
        testid="cb-buyer-premium"
      />
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
        value={showStripe ? fmt(fee.buyer_total_charged, currency) : fmt(fee.hammer_price + fee.buyer_premium + fee.buyer_taxes, currency)}
        bold
        testid="cb-total"
      />
    </div>
  );
};

export default CostBreakdown;
