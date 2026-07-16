import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { DollarSign, CheckCircle2, Info, Sparkles, ShieldCheck, Receipt } from 'lucide-react';
import { toast } from 'sonner';
import { formatCurrency } from '../utils/currencyFormatter';
import PushNotificationToggle from './PushNotificationToggle';
import InfoTip from './InfoTip';

const API = API_BASE;

/**
 * BidConfirmationDialog - Shows transparent cost breakdown before placing a bid
 * Implements "Radical Transparency" from the Disruptor Protocol
 * 
 * Features:
 * - Calls /api/payments/tax/calculate to get real-time cost breakdown with Quebec taxes
 * - Shows Hammer Price, Buyer Premium, Platform Fee (vehicles), Tax breakdown
 * - Highlights "Private Sale" status for individual sellers (no tax on item)
 * - Shows vehicle exception note (BidVex fees only, hammer paid to seller)
 * - Shows total out-of-pocket cost
 */
const BidConfirmationDialog = ({ 
  isOpen, 
  onClose, 
  onConfirm, 
  bidAmount, 
  listingTitle,
  category = 'general',
  sellerIsBusiness = true,
  buyerTier = 'basic',
  sellerTier = 'basic',
  region = 'QC',
  loading = false,
  buyersPremiumRate = null,
  // Spec Feature 4 — bid disclaimer + deposit notice
  currency = 'CAD',
  paymentMethod = 'stripe',
  requiresDeposit = false,
  depositAmount = 0,
  depositType = 'fixed',
  // iter292 — Explicit vehicle-listing flag derived from the LISTING'S
  // collection (vehicle_listings) rather than category text. A dealer
  // selling an "auto-grade tool" on Marketplace must NOT trigger the
  // vehicle-only fee/tax block here.
  isVehicleListing = false,
  // iter343 BUG-6 — lot quantity semantics (bid model):
  //   default → bid is a PER-LOT TOTAL covering all N items
  //   multiplyByQuantity → bid is PER ITEM (effective hammer = bid × qty)
  quantity = 1,
  multiplyByQuantity = false,
}) => {
  const [costBreakdown, setCostBreakdown] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState(null);

  const qty = Math.max(1, parseInt(quantity, 10) || 1);
  const perItem = multiplyByQuantity && qty > 1;
  const effectiveHammer = perItem ? bidAmount * qty : bidAmount;

  // iter292 — Authoritative source: the explicit prop set by the call
  // site (true only on VehicleDetailPage). Category text matching
  // bled into Marketplace/Lots listings whose names happened to
  // include words like 'auto' or 'truck'.
  const isVehicle = !!isVehicleListing;

  // iter221 Task 3 — Single source of truth for tier→buyer-premium-rate
  // resolution. Removes the legacy `|| 0.05` hardcoded fallback that masked
  // the correct VIP rate (0.03) and Premium rate (0.035) whenever the
  // backend response was slow / missing. Mirrors the backend tables in
  // `services/fee_calculator.py::INDIVIDUAL_BUYER_RATES` + `TIER_ALIASES`.
  const resolveBuyerPremiumRate = () => {
    // Listing-level override always wins (custom premium set by seller).
    if (typeof buyersPremiumRate === 'number' && buyersPremiumRate >= 0) {
      return buyersPremiumRate;
    }
    // If the API breakdown carried a rate, use it verbatim — note we
    // intentionally do NOT use `||` here (which falsy-treats 0) but
    // an explicit `typeof number` check so 0 (some partner sellers) is
    // honoured.
    if (costBreakdown && typeof costBreakdown.buyer_premium_rate === 'number') {
      return costBreakdown.buyer_premium_rate;
    }
    // Tier-derived fallback (mirrors backend, no 0.05 default).
    const TIER_RATES = { standard: 0.050, premium: 0.035, vip_elite: 0.030 };
    const TIER_ALIASES = { vip: 'vip_elite', free: 'standard', basic: 'standard', starter: 'standard' };
    const t = String(buyerTier || '').toLowerCase().trim() || 'standard';
    const norm = TIER_ALIASES[t] || t;
    return TIER_RATES[norm] ?? TIER_RATES.standard;
  };
  const effectivePremiumRate = resolveBuyerPremiumRate();

  // Fetch cost breakdown when dialog opens or bid amount changes
  useEffect(() => {
    if (isOpen && bidAmount > 0) {
      fetchCostBreakdown();
    }
  }, [isOpen, bidAmount, sellerIsBusiness, category, buyerTier, sellerTier, buyersPremiumRate]);

  const fetchCostBreakdown = async () => {
    setCalculating(true);
    setError(null);
    
    try {
      const response = await axios.post(`${API}/payments/tax/calculate`, {
        hammer_price: effectiveHammer,
        category: category,
        buyer_tier: buyerTier,
        seller_tier: sellerTier,
        seller_is_business: sellerIsBusiness,
        buyers_premium_rate: buyersPremiumRate
      });
      
      setCostBreakdown(response.data);
    } catch (err) {
      console.error('Failed to fetch cost breakdown:', err);
      setError('Unable to calculate costs. Please try again.');

      // iter221 Task 3 — Network-failure fallback. We pre-compute the rate
      // via the same helper as the success path so VIP/Premium users see
      // their correct rate even when the tax/calculate API is unreachable.
      // The legacy `?? 0.05` shortcut was the actual source of the production
      // discrepancy (it could win over the tier table when buyer_premium_rate
      // was undefined in the response shape).
      const buyerPremium = bidAmount * effectivePremiumRate;
      const platformFee = isVehicle ? bidAmount * 0.025 : 0;
      const taxRate = 0.14975; // Quebec GST + QST
      const taxOnHammer = sellerIsBusiness && !isVehicle ? bidAmount * taxRate : 0;
      const taxOnFees = (buyerPremium + platformFee) * taxRate;

      setCostBreakdown({
        payment_type: isVehicle ? 'vehicle' : 'general',
        hammer_price: bidAmount,
        buyer_premium: buyerPremium,
        buyer_premium_rate: effectivePremiumRate,
        platform_fee: platformFee,
        bidvex_fees_subtotal: buyerPremium + platformFee,
        bidvex_fees_tax_total: taxOnFees,
        hammer_tax_applicable: sellerIsBusiness && !isVehicle,
        buyer_pays_hammer_tax: taxOnHammer,
        buyer_pays_fees_tax: taxOnFees,
        buyer_total: bidAmount + buyerPremium + taxOnHammer + taxOnFees,
        stripe_charge_total: isVehicle ? buyerPremium + platformFee + taxOnFees : bidAmount + buyerPremium + taxOnHammer + taxOnFees,
        seller_balance_due: isVehicle ? bidAmount : undefined,
        tax_savings: !sellerIsBusiness && !isVehicle ? bidAmount * taxRate : 0
      });
    } finally {
      setCalculating(false);
    }
  };

  const isPrivateSale = !sellerIsBusiness && !isVehicle;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md max-w-[calc(100vw-2rem)] flex flex-col gap-3" data-testid="bid-confirmation-dialog">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Receipt className="h-5 w-5 text-[#06B6D4]" />
            Confirm Your Bid
          </DialogTitle>
          <DialogDescription>
            Review your total cost before placing your bid on &quot;{listingTitle}&quot;
          </DialogDescription>
        </DialogHeader>

        {/* Private Sale Badge */}
        {isPrivateSale && (
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-4 mb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-green-600" />
              <span className="font-semibold text-green-700">🎉 Private Sale: Save on Taxes!</span>
            </div>
            <p className="text-sm text-green-600 mt-1">
              This item is from an individual seller - no sales tax on the hammer price!
            </p>
          </div>
        )}

        {/* Cost Breakdown */}
        <div className="space-y-4 py-4">
          {calculating ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-4 border-[#06B6D4] border-t-transparent"></div>
            </div>
          ) : costBreakdown ? (
            <>
              {/* iter343 BUG-6 — quantity always visible for multi-item lots */}
              {qty > 1 && (
                <div className="flex justify-between items-center" data-testid="bid-confirm-quantity">
                  <span className="text-sm font-medium">Quantity</span>
                  <span className="font-semibold">{qty} items</span>
                </div>
              )}
              {perItem && (
                <div className="flex justify-between items-center text-sm" data-testid="bid-confirm-per-item">
                  <span className="text-muted-foreground">Your bid (per item)</span>
                  <span>{formatCurrency(bidAmount)}</span>
                </div>
              )}
              {/* Hammer Price */}
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    {perItem
                      ? `Hammer Price (${qty} × ${formatCurrency(bidAmount)})`
                      : qty > 1
                        ? `Hammer Price (total for ${qty} items)`
                        : 'Hammer Price'}
                  </span>
                  <Badge variant="outline" className="text-xs">Your Bid</Badge>
                </div>
                <span className="font-semibold">{formatCurrency(costBreakdown.hammer_price)}</span>
              </div>

              {/* Buyer Premium — iter221 Task 3: pct sourced from
                  effectivePremiumRate (tier-aware) so VIP users see 3.0%
                  and Premium see 3.5% with no 0.05 hardcoded fallback. */}
              <div className="flex justify-between items-center text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">
                    Buyer&apos;s Premium ({(effectivePremiumRate * 100).toFixed(1)}%)
                  </span>
                  <InfoTip en="A standard platform fee added to winning bids. Your tier determines the rate." fr="Frais de plateforme standard ajoutés aux enchères gagnantes. Votre niveau détermine le taux." />
                </div>
                <span data-testid="bid-buyer-premium">{formatCurrency(costBreakdown.buyer_premium)}</span>
              </div>

              {/* Platform Fee (Vehicles only) */}
              {isVehicle && costBreakdown.platform_fee > 0 && (
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Platform Fee (2.5%)</span>
                  <span>{formatCurrency(costBreakdown.platform_fee)}</span>
                </div>
              )}

              <Separator />

              {/* Tax Section */}
              {isVehicle ? (
                <>
                  {/* Vehicle: Tax only on BidVex fees */}
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground">Tax on BidVex Fees (GST/QST)</span>
                    <span>{formatCurrency(costBreakdown.bidvex_fees_tax_total)}</span>
                  </div>
                </>
              ) : (
                <>
                  {/* Tax on Item */}
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground">Tax on Item (GST/QST)</span>
                    {isPrivateSale ? (
                      <div className="flex items-center gap-2">
                        <span className="line-through text-gray-400">
                          {formatCurrency(costBreakdown.tax_savings || 0)}
                        </span>
                        <Badge className="bg-green-100 text-green-700 text-xs">
                          $0.00
                        </Badge>
                      </div>
                    ) : (
                      <span>{formatCurrency(costBreakdown.buyer_pays_hammer_tax || 0)}</span>
                    )}
                  </div>

                  {/* Tax on Fees */}
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground">Tax on Fees</span>
                    <span>{formatCurrency(costBreakdown.buyer_pays_fees_tax || 0)}</span>
                  </div>
                </>
              )}

              {/* Tax Savings Banner (Private Sale - General only) */}
              {isPrivateSale && (costBreakdown.tax_savings || 0) > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-green-600" />
                      <span className="text-sm font-medium text-green-700">Your Savings</span>
                    </div>
                    <span className="font-bold text-green-700">
                      -{formatCurrency(costBreakdown.tax_savings || 0)}
                    </span>
                  </div>
                </div>
              )}

              <Separator className="my-2" />

              {/* Vehicle Payment Note */}
              {isVehicle && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-2">
                  <div className="flex items-start gap-2">
                    <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                    <div className="text-sm">
                      <p className="font-medium text-blue-700">Vehicle Payment</p>
                      <p className="text-blue-600 mt-1">
                        Only BidVex fees and taxes are paid online. Hammer price ({formatCurrency(bidAmount)}) paid directly to seller via Bank Draft.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Total Estimated Price */}
              <div className="bg-gradient-to-r from-[#1E3A8A]/10 to-[#06B6D4]/10 rounded-lg p-4" data-testid="bid-total-estimated">
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-bold text-lg">
                      {isVehicle ? 'Pay Now via Stripe' : 'Total Estimated Price'}
                    </span>
                    <p className="text-xs text-muted-foreground">
                      {isVehicle ? 'BidVex fees + taxes only' : 'Bid + Premium + Taxes'}
                    </p>
                  </div>
                  <span className="text-2xl font-bold text-[#1E3A8A]" data-testid="bid-total-amount">
                    {formatCurrency(isVehicle ? costBreakdown.stripe_charge_total : costBreakdown.buyer_total)}
                  </span>
                </div>
              </div>

              {/* Balance Due to Seller (Vehicles) */}
              {isVehicle && costBreakdown.seller_balance_due && (
                <div className="bg-slate-100 rounded-lg p-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-slate-600">Balance due to seller (Bank Draft)</span>
                    <span className="font-bold text-slate-800">
                      {formatCurrency(costBreakdown.seller_balance_due)}
                    </span>
                  </div>
                </div>
              )}
            </>
          ) : error ? (
            <div className="text-center py-4 text-red-500">
              {error}
            </div>
          ) : null}
        </div>

        {/* Push notification prompt — shown inside bid dialog */}
        <div className="px-1 pb-2">
          <PushNotificationToggle variant="prompt" />
        </div>

        {/* Spec Feature 4 — Bid Transparency Disclaimer */}
        <div className="px-1 pb-2">
          <div className="bg-rose-50 border border-rose-200 rounded-md p-3 text-xs leading-relaxed" data-testid="bid-disclaimer">
            <p className="font-semibold text-rose-900 mb-1">Bid Disclaimer · Avis d'enchère</p>
            <p className="text-rose-800">
              <strong>EN:</strong> By placing a bid, you agree that if you are the winning bidder at auction close, you are legally obligated to complete the purchase. Your card on file will be charged in <strong>{currency}</strong> according to the seller's payment method ({paymentMethod}) and BidVex's fee schedule shown above. Bids cannot be retracted once placed.
            </p>
            <p className="text-rose-800 mt-1">
              <strong>FR:</strong> En plaçant une enchère, vous acceptez que si vous êtes l'enchérisseur gagnant à la clôture, vous êtes légalement tenu de finaliser l'achat. Votre carte sera débitée en <strong>{currency}</strong> selon le mode de paiement du vendeur et la grille tarifaire BidVex ci-dessus. Les offres ne peuvent pas être retirées.
            </p>
            {requiresDeposit && depositAmount > 0 && (
              <p className="text-rose-900 mt-2 font-semibold" data-testid="bid-deposit-notice">
                ⚠️ Deposit required · Dépôt requis: {depositType === 'percentage'
                  ? `${depositAmount}% of starting bid`
                  : `$${Number(depositAmount).toFixed(2)} ${currency}`}
                {' '}— charged immediately upon placing your first bid on this auction.
              </p>
            )}
          </div>

          {/* iter355 H-1 — Refundable pre-authorization hold notice */}
          {!isVehicle && bidAmount > 500 && (() => {
            const holdRaw = bidAmount * 0.10;
            const holdCad = Math.max(50, Math.min(500, holdRaw));
            return (
              <div
                className="mt-2 bg-blue-50 border border-blue-200 rounded-md p-3 text-xs leading-relaxed"
                data-testid="bid-preauth-hold-notice"
              >
                <div className="flex items-start gap-2">
                  <ShieldCheck className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-blue-900 mb-1">
                      Refundable Hold · Dépôt de garantie remboursable
                    </p>
                    <p className="text-blue-800">
                      <strong>EN:</strong> A fully-refundable hold of{' '}
                      <strong data-testid="bid-preauth-hold-amount">
                        ${holdCad.toFixed(0)} CAD
                      </strong>{' '}
                      will be temporarily placed on your card while your bid leads.
                      Released instantly if you are outbid. If you win, the hold
                      transfers toward final payment at checkout.
                    </p>
                    <p className="text-blue-800 mt-1">
                      <strong>FR:</strong> Un dépôt de garantie entièrement
                      remboursable de{' '}
                      <strong>${holdCad.toFixed(0)} CAD</strong>{' '}
                      sera temporairement bloqué sur votre carte pendant que votre
                      enchère est en tête. Libéré instantanément si vous êtes surenchéri.
                      Si vous gagnez, le dépôt est appliqué au paiement final.
                    </p>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>

        <DialogFooter className="flex flex-col sm:flex-row gap-2 sticky bottom-0 -mx-6 -mb-6 px-6 py-3 bg-background border-t z-10" data-testid="bid-confirmation-footer">
          <Button variant="outline" onClick={onClose} disabled={loading} className="w-full sm:w-auto" data-testid="bid-cancel-btn">
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={loading || calculating}
            className="w-full sm:w-auto bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white"
            data-testid="bid-confirm-btn"
          >
            {loading ? (
              'Placing Bid...'
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Confirm Bid {formatCurrency(bidAmount)}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default BidConfirmationDialog;
