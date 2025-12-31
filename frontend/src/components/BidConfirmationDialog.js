import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { DollarSign, CheckCircle2, Info, Sparkles, ShieldCheck, Receipt } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * BidConfirmationDialog - Shows transparent cost breakdown before placing a bid
 * Implements "Radical Transparency" from the Disruptor Protocol
 * 
 * Features:
 * - Calls /api/fees/calculate-buyer-cost to get real-time cost breakdown
 * - Shows Hammer Price, Buyer Premium (5%), Tax breakdown
 * - Highlights "Private Sale" status for individual sellers (no tax on item)
 * - Shows total out-of-pocket cost
 */
const BidConfirmationDialog = ({ 
  isOpen, 
  onClose, 
  onConfirm, 
  bidAmount, 
  listingTitle,
  sellerIsBusiness = true, // Default to business (tax applies)
  region = 'QC',
  loading = false
}) => {
  const [costBreakdown, setCostBreakdown] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState(null);

  // Fetch cost breakdown when dialog opens or bid amount changes
  useEffect(() => {
    if (isOpen && bidAmount > 0) {
      fetchCostBreakdown();
    }
  }, [isOpen, bidAmount, sellerIsBusiness, region]);

  const fetchCostBreakdown = async () => {
    setCalculating(true);
    setError(null);
    
    try {
      const response = await axios.get(`${API}/fees/calculate-buyer-cost`, {
        params: {
          amount: bidAmount,
          region: region,
          seller_is_business: sellerIsBusiness
        }
      });
      
      setCostBreakdown(response.data);
    } catch (err) {
      console.error('Failed to fetch cost breakdown:', err);
      setError('Unable to calculate costs. Please try again.');
      
      // Fallback calculation if API fails
      const buyerPremium = bidAmount * 0.05;
      const taxRate = 0.14975; // Quebec GST + QST
      const taxOnHammer = sellerIsBusiness ? bidAmount * taxRate : 0;
      const taxOnPremium = buyerPremium * taxRate;
      
      setCostBreakdown({
        hammer_price: bidAmount,
        buyer_premium: buyerPremium,
        tax_on_hammer: taxOnHammer,
        tax_on_premium: taxOnPremium,
        tax: taxOnHammer + taxOnPremium,
        total: bidAmount + buyerPremium + taxOnHammer + taxOnPremium,
        seller_type: sellerIsBusiness ? 'business' : 'individual',
        tax_savings: sellerIsBusiness ? 0 : bidAmount * taxRate
      });
    } finally {
      setCalculating(false);
    }
  };

  const isPrivateSale = !sellerIsBusiness;

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
                <span className="font-semibold">${costBreakdown.hammer_price?.toFixed(2)}</span>
              </div>

              {/* Buyer Premium */}
              <div className="flex justify-between items-center text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">Buyer's Premium (5%)</span>
                  <Info className="h-3 w-3 text-muted-foreground cursor-help" title="Standard platform fee" />
                </div>
                <span>${costBreakdown.buyer_premium?.toFixed(2)}</span>
              </div>

              <Separator />

              {/* Tax on Item */}
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Tax on Item (GST/QST)</span>
                {isPrivateSale ? (
                  <div className="flex items-center gap-2">
                    <span className="line-through text-gray-400">
                      ${costBreakdown.tax_savings?.toFixed(2)}
                    </span>
                    <Badge className="bg-green-100 text-green-700 text-xs">
                      $0.00
                    </Badge>
                  </div>
                ) : (
                  <span>${costBreakdown.tax_on_hammer?.toFixed(2)}</span>
                )}
              </div>

              {/* Tax on Premium */}
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Tax on Premium</span>
                <span>${costBreakdown.tax_on_premium?.toFixed(2)}</span>
              </div>

              <Separator />

              {/* Total Tax */}
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Total Tax</span>
                <span>${costBreakdown.tax?.toFixed(2)}</span>
              </div>

              {/* Tax Savings Banner (Private Sale) */}
              {isPrivateSale && costBreakdown.tax_savings > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-green-600" />
                      <span className="text-sm font-medium text-green-700">Your Savings</span>
                    </div>
                    <span className="font-bold text-green-700">
                      -${costBreakdown.tax_savings?.toFixed(2)}
                    </span>
                  </div>
                </div>
              )}

              <Separator className="my-2" />

              {/* Total Out-of-Pocket */}
              <div className="bg-gradient-to-r from-[#1E3A8A]/10 to-[#06B6D4]/10 rounded-lg p-4">
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-bold text-lg">Total Out-of-Pocket</span>
                    <p className="text-xs text-muted-foreground">Final cost if you win</p>
                  </div>
                  <span className="text-2xl font-bold text-[#1E3A8A]">
                    ${costBreakdown.total?.toFixed(2)}
                  </span>
                </div>
              </div>
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
                Confirm Bid ${bidAmount?.toFixed(2)}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default BidConfirmationDialog;
