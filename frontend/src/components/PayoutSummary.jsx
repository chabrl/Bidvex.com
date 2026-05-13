/**
 * iter209 Step 5 — Seller Payout Summary component (single source of truth UI)
 *
 * Renders the seller-side breakdown for a closed auction, in 4 shapes:
 *
 *   INDIVIDUAL SELLER:
 *     Hammer Price Won, BidVex Commission, GST, QST, Your Payout
 *
 *   PARTNER:
 *     Hammer Price, Your BP, Subtotal, BidVex 3%, GST, QST, Your Payout
 *     (cash/e-transfer note: "Commission charged to your card on file.")
 *
 *   VEHICLE DEALER:
 *     Sale Price, Your Commission $0.00, Your Payout = full hammer
 *
 *   STORAGE FACILITY:
 *     Winning Bid, 5% commission, GST, QST, Stripe, Net You Keep
 *     (note: facility receives nothing via Stripe — this is the auto-charge breakdown)
 *
 * Backed by the same `/api/fees/v2/preview` endpoint — math is identical to
 * what the buyer sees in <CostBreakdown>.
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

export const PayoutSummary = ({
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
      <div className={`rounded-lg border border-slate-200 dark:border-slate-700/40 bg-slate-50 dark:bg-slate-900/40 p-3 text-xs text-slate-500 flex items-center gap-2 ${className}`} data-testid="payout-summary-loading">
        <Loader2 className="w-3 h-3 animate-spin" /> {isFr ? 'Calcul…' : 'Calculating…'}
      </div>
    );
  }

  const wrapperCls = `rounded-lg border border-slate-200 dark:border-slate-700/40 bg-white dark:bg-slate-900/40 p-4 ${className}`;
  const accountKind = sellerAccountType;
  const commPct = (fee.seller_commission_rate * 100).toFixed(2).replace(/\.?0+$/, '');

  // ── Vehicle dealer — full hammer, $0 commission ──────────────────────
  if (accountKind === 'vehicle_dealer') {
    return (
      <div className={wrapperCls} data-testid="payout-summary-vehicle_dealer">
        <Row label={isFr ? 'Prix de vente' : 'Sale Price'} value={fmt(fee.hammer_price, currency)} testid="ps-sale" />
        <Row label={isFr ? 'Votre commission' : 'Your Commission'} value="$0.00" mute testid="ps-comm-zero" />
        <Row label={isFr ? 'Votre paiement' : 'Your Payout'} value={fmt(fee.seller_payout, currency)} bold testid="ps-payout" />
        <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-2">
          {isFr
            ? "(L'acheteur a déjà payé les frais de plateforme. Frais annuels de 100 $ facturés séparément.)"
            : '(Buyer already paid the platform fee. Annual $100 fee billed separately.)'}
        </p>
      </div>
    );
  }

  // ── Storage facility — iter211 P0: two sub-scenarios by payment method ──
  //  • cash / e-transfer → BidVex auto-charges facility card 5%+GST+QST+Stripe
  //  • stripe            → 5%+GST+QST deducted from facility's Stripe payout
  if (accountKind === 'storage_facility') {
    const isStripe = fee.charge_buyer_via_stripe === true;
    return (
      <div className={wrapperCls} data-testid="payout-summary-storage_facility">
        <Row label={isFr ? 'Enchère gagnante' : 'Winning Bid'} value={fmt(fee.hammer_price, currency)} testid="ps-hammer" />
        <Row label={isFr ? `Commission BidVex (${commPct} %)` : `BidVex Commission (${commPct}%)`} value={`-${fmt(fee.seller_commission, currency)}`} testid="ps-comm" />
        <Row label={isFr ? 'TPS sur commission' : 'GST on Commission'} value={`-${fmt(fee.seller_gst, currency)}`} testid="ps-gst" />
        <Row label={isFr ? 'TVQ sur commission' : 'QST on Commission'} value={`-${fmt(fee.seller_qst, currency)}`} testid="ps-qst" />
        {!isStripe && (
          <Row label={isFr ? 'Traitement Stripe' : 'Stripe Processing'} value={`-${fmt(fee.seller_stripe_fee, currency)}`} testid="ps-stripe" />
        )}
        {isStripe ? (
          <Row
            label={isFr ? 'Votre paiement net' : 'Your Net Payout'}
            value={fmt(fee.seller_payout, currency)}
            bold
            testid="ps-payout"
          />
        ) : (
          <Row
            label={isFr ? 'Montant facturé à votre carte' : 'Charged to Your Card'}
            value={fmt(fee.seller_commission_total + fee.seller_stripe_fee, currency)}
            bold
            testid="ps-charged"
          />
        )}
        <div className="mt-2 text-[11px] text-amber-700 dark:text-amber-400 flex items-start gap-1.5" data-testid="ps-storage-msg">
          <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>
            {isStripe ? (
              isFr
                ? "L'acheteur a payé via Stripe. Vous absorbez la commission de 5 %, déduite directement de votre versement."
                : 'Buyer paid via Stripe. The 5% commission is absorbed by you and deducted from your Stripe payout.'
            ) : (
              isFr
                ? "L'acheteur vous paie directement le montant total de l'enchère. BidVex facture la commission à votre carte enregistrée."
                : 'The buyer pays you the full winning bid directly. BidVex charges the commission to your card on file.'
            )}
          </span>
        </div>
      </div>
    );
  }

  // ── Partner — has 3 modes (stripe / cash / e_transfer) ────────────────
  if (accountKind === 'partner') {
    const isCash = !fee.charge_buyer_via_stripe;
    return (
      <div className={wrapperCls} data-testid="payout-summary-partner">
        <Row label={isFr ? 'Prix au marteau' : 'Hammer Price'} value={fmt(fee.hammer_price, currency)} testid="ps-hammer" />
        <Row label={isFr ? `Votre prime (${(fee.buyer_premium_rate * 100).toFixed(2).replace(/\.?0+$/, '')} %)` : `Your Buyer's Premium (${(fee.buyer_premium_rate * 100).toFixed(2).replace(/\.?0+$/, '')}%)`} value={`+${fmt(fee.buyer_premium, currency)}`} testid="ps-bp" />
        <Row label={isFr ? 'Sous-total' : 'Subtotal'} value={fmt(fee.hammer_price + fee.buyer_premium, currency)} testid="ps-subtotal" />
        <Row label={isFr ? `Commission BidVex (${commPct} %)` : `BidVex Commission (${commPct}%)`} value={`-${fmt(fee.seller_commission, currency)}`} testid="ps-comm" />
        <Row label={isFr ? 'TPS sur commission' : 'GST on Commission'} value={`-${fmt(fee.seller_gst, currency)}`} testid="ps-gst" />
        <Row label={isFr ? 'TVQ sur commission' : 'QST on Commission'} value={`-${fmt(fee.seller_qst, currency)}`} testid="ps-qst" />
        <Row label={isFr ? 'Votre paiement' : 'Your Payout'} value={fmt(fee.seller_payout, currency)} bold testid="ps-payout" />
        {isCash && (
          <div className="mt-2 text-[11px] text-amber-700 dark:text-amber-400 flex items-start gap-1.5" data-testid="ps-cash-msg">
            <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            <span>
              {isFr
                ? 'Commission débitée sur votre carte enregistrée.'
                : 'Commission charged to your card on file.'}
            </span>
          </div>
        )}
      </div>
    );
  }

  // ── Individual — default ─────────────────────────────────────────────
  return (
    <div className={wrapperCls} data-testid="payout-summary-individual">
      <Row label={isFr ? 'Prix au marteau' : 'Hammer Price Won'} value={fmt(fee.hammer_price, currency)} testid="ps-hammer" />
      <Row label={isFr ? `Commission BidVex (${commPct} %)` : `BidVex Commission (${commPct}%)`} value={`-${fmt(fee.seller_commission, currency)}`} testid="ps-comm" />
      <Row label={isFr ? 'TPS sur commission' : 'GST on Commission'} value={`-${fmt(fee.seller_gst, currency)}`} testid="ps-gst" />
      <Row label={isFr ? 'TVQ sur commission' : 'QST on Commission'} value={`-${fmt(fee.seller_qst, currency)}`} testid="ps-qst" />
      <Row label={isFr ? 'Votre paiement' : 'Your Payout'} value={fmt(fee.seller_payout, currency)} bold testid="ps-payout" />
    </div>
  );
};

export default PayoutSummary;
