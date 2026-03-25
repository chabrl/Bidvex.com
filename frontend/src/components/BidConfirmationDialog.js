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
  buyersPremiumRate = null
}) => {
  const [costBreakdown, setCostBreakdown] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState(null);

  const isVehicle = ['vehicle', 'car', 'auto', 'automobile', 'truck', 'motorcycle', 'suv', 'van']
    .some(keyword => (category || '').toLowerCase().includes(keyword));

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
        hammer_price: bidAmount,
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
      
      // Fallback calculation if API fails
      const effectivePremiumRate = buyersPremiumRate ?? 0.05;
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
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
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
              {/* Hammer Price */}
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Hammer Price</span>
                  <Badge variant="outline" className="text-xs">Your Bid</Badge>
                </div>
                <span className="font-semibold">{formatCurrency(costBreakdown.hammer_price)}</span>
              </div>

              {/* Buyer Premium */}
              <div className="flex justify-between items-center text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">
                    Buyer&apos;s Premium ({((costBreakdown.buyer_premium_rate || 0.05) * 100).toFixed(1)}%)
                  </span>
                  <Info className="h-3 w-3 text-muted-foreground cursor-help" title="Standard platform fee" />
                </div>
                <span>{formatCurrency(costBreakdown.buyer_premium)}</span>
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

        <DialogFooter className="flex gap-2">
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={loading || calculating}
            className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white"
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
