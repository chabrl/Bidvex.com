import API_BASE from '../../config';
/**
 * PricingCalculator.js
 * Real-time total cost calculator for vehicle auctions
 * Shows buyer premium, fees, taxes, and subscription savings
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Separator } from '../ui/separator';
import {
  Calculator, DollarSign, Info, TrendingDown, Award,
  ChevronDown, ChevronUp, Percent, Receipt, Building2,
  CreditCard, HelpCircle
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

// Format currency
const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
  }).format(amount || 0);
};

// Fee tier configurations
const FEE_TIERS = {
  buyer: {
    free: { rate: 5.0, label: 'Standard', color: 'text-slate-600' },
    premium: { rate: 3.5, label: 'Premium', color: 'text-blue-600', savings: 1.5 },
    vip: { rate: 3.0, label: 'VIP Elite', color: 'text-amber-600', savings: 2.0 }
  },
  seller: {
    free: { rate: 4.0, label: 'Standard', color: 'text-slate-600' },
    premium: { rate: 2.5, label: 'Premium', color: 'text-blue-600', savings: 1.5 },
    vip: { rate: 2.0, label: 'VIP Elite', color: 'text-amber-600', savings: 2.0 }
  }
};

// Platform fee (constant)
const PLATFORM_FEE_RATE = 2.5;

// Tax rates by province
const TAX_RATES = {
  ON: { type: 'HST', rate: 13 },
  NS: { type: 'HST', rate: 15 },
  NB: { type: 'HST', rate: 15 },
  NL: { type: 'HST', rate: 15 },
  PE: { type: 'HST', rate: 15 },
  BC: { type: 'GST+PST', gst: 5, pst: 7, rate: 12 },
  SK: { type: 'GST+PST', gst: 5, pst: 6, rate: 11 },
  MB: { type: 'GST+PST', gst: 5, pst: 7, rate: 12 },
  QC: { type: 'GST+QST', gst: 5, qst: 9.975, rate: 14.975 },
  AB: { type: 'GST', rate: 5 },
  YT: { type: 'GST', rate: 5 },
  NT: { type: 'GST', rate: 5 },
  NU: { type: 'GST', rate: 5 }
};

// Savings Calculator Component
export const SavingsDisplay = ({ bidAmount, currentTier }) => {
  if (currentTier === 'vip') return null;

  const currentRate = FEE_TIERS.buyer[currentTier]?.rate || 5.0;
  const premiumRate = FEE_TIERS.buyer.premium.rate;
  const vipRate = FEE_TIERS.buyer.vip.rate;

  const premiumSavings = (currentRate - premiumRate) * bidAmount / 100;
  const vipSavings = (currentRate - vipRate) * bidAmount / 100;

  return (
    <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-950/30 dark:to-purple-950/30 rounded-lg p-4 border border-blue-100 dark:border-blue-800">
      <div className="flex items-center gap-2 mb-3">
        <TrendingDown className="h-5 w-5 text-blue-600" />
        <span className="font-semibold text-blue-800 dark:text-blue-200">Subscription Savings</span>
      </div>
      
      <div className="space-y-2 text-sm">
        {currentTier === 'free' && (
          <div className="flex justify-between items-center">
            <span className="text-slate-600 dark:text-slate-400">
              With Premium (3.5% fee)
            </span>
            <span className="text-green-600 font-semibold">
              Save {formatCurrency(premiumSavings)}
            </span>
          </div>
        )}
        <div className="flex justify-between items-center">
          <span className="text-slate-600 dark:text-slate-400">
            With VIP Elite (3% fee)
          </span>
          <span className="text-green-600 font-semibold">
            Save {formatCurrency(vipSavings)}
          </span>
        </div>
      </div>
      
      <Button 
        variant="outline" 
        size="sm" 
        className="w-full mt-3 text-blue-600 border-blue-300 hover:bg-blue-50"
        onClick={() => window.location.href = '/settings?tab=subscription'}
      >
        <Award className="h-4 w-4 mr-2" />
        Upgrade & Save
      </Button>
    </div>
  );
};

// Fee Tier Comparison Component
export const FeeTierComparison = ({ bidAmount, type = 'buyer' }) => {
  const tiers = FEE_TIERS[type];
  
  return (
    <div className="grid grid-cols-3 gap-2 text-center">
      {Object.entries(tiers).map(([tier, config]) => {
        const feeAmount = (config.rate * bidAmount) / 100;
        return (
          <div 
            key={tier}
            className={`p-3 rounded-lg border ${tier === 'free' ? 'bg-slate-50 border-slate-200' : tier === 'premium' ? 'bg-blue-50 border-blue-200' : 'bg-amber-50 border-amber-200'}`}
          >
            <p className={`text-xs font-medium ${config.color}`}>{config.label}</p>
            <p className="text-lg font-bold mt-1">{config.rate}%</p>
            <p className="text-xs text-slate-500">{formatCurrency(feeAmount)}</p>
          </div>
        );
      })}
    </div>
  );
};

// Main Pricing Calculator Component
export const PricingCalculator = ({ 
  vehicleId, 
  bidAmount: initialBidAmount, 
  province = 'ON',
  showInput = true,
  expanded: initialExpanded = false 
}) => {
  const { user, token } = useAuth();
  const { t } = useTranslation();
  const [bidAmount, setBidAmount] = useState(initialBidAmount || 0);
  const [expanded, setExpanded] = useState(initialExpanded);
  const [breakdown, setBreakdown] = useState(null);
  const [loading, setLoading] = useState(false);

  const subscriptionTier = user?.subscription_tier || 'free';

  // Calculate breakdown locally for instant updates
  const calculateLocalBreakdown = useCallback((amount) => {
    const tier = FEE_TIERS.buyer[subscriptionTier] || FEE_TIERS.buyer.free;
    const taxConfig = TAX_RATES[province] || TAX_RATES.ON;

    const buyerPremium = (amount * tier.rate) / 100;
    const platformFee = (amount * PLATFORM_FEE_RATE) / 100;
    const subtotal = amount + buyerPremium + platformFee;
    
    let taxes = {
      type: taxConfig.type,
      gst: 0,
      pst: 0,
      qst: 0,
      hst: 0,
      total: 0
    };

    if (taxConfig.type === 'HST') {
      taxes.hst = (subtotal * taxConfig.rate) / 100;
      taxes.total = taxes.hst;
    } else if (taxConfig.type === 'GST') {
      taxes.gst = (subtotal * taxConfig.rate) / 100;
      taxes.total = taxes.gst;
    } else if (taxConfig.type === 'GST+PST') {
      taxes.gst = (subtotal * taxConfig.gst) / 100;
      taxes.pst = (subtotal * taxConfig.pst) / 100;
      taxes.total = taxes.gst + taxes.pst;
    } else if (taxConfig.type === 'GST+QST') {
      taxes.gst = (subtotal * taxConfig.gst) / 100;
      taxes.qst = (subtotal * taxConfig.qst) / 100;
      taxes.total = taxes.gst + taxes.qst;
    }

    return {
      hammer_price: amount,
      buyer_premium: {
        rate: `${tier.rate}%`,
        amount: buyerPremium
      },
      platform_fee: {
        rate: `${PLATFORM_FEE_RATE}%`,
        amount: platformFee
      },
      subtotal_before_tax: subtotal,
      taxes,
      total_payable: subtotal + taxes.total,
      subscription_tier: subscriptionTier,
      province
    };
  }, [subscriptionTier, province]);

  // Update breakdown when amount changes
  useEffect(() => {
    if (bidAmount > 0) {
      setBreakdown(calculateLocalBreakdown(bidAmount));
    }
  }, [bidAmount, calculateLocalBreakdown]);

  // Fetch from backend for accurate calculation
  const fetchBackendBreakdown = async () => {
    if (!vehicleId || !bidAmount || bidAmount <= 0) return;
    
    setLoading(true);
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await axios.post(
        `${API}/vehicles/${vehicleId}/pricing-breakdown?bid_amount=${bidAmount}`,
        {},
        { headers }
      );
      setBreakdown(response.data.breakdown);
    } catch (error) {
      console.error('Failed to fetch pricing breakdown:', error);
    } finally {
      setLoading(false);
    }
  };

  if (showInput && bidAmount <= 0 && !breakdown) {
    return (
      <Card className="border-dashed" data-testid="pricing-calculator">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-slate-500">
            <Calculator className="h-5 w-5" />
            <span>{t("fees.enterBidAmount")}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-blue-100 dark:border-blue-900" data-testid="pricing-calculator">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Receipt className="h-5 w-5 text-blue-600" />
            Total Cost Breakdown
          </CardTitle>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => setExpanded(!expanded)}
            className="h-8"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Input */}
        {showInput && (
          <div className="flex gap-2">
            <div className="relative flex-1">
              <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                type="number"
                value={bidAmount || ''}
                onChange={(e) => setBidAmount(parseFloat(e.target.value) || 0)}
                placeholder="Enter bid amount"
                className="pl-9"
              />
            </div>
            <Button 
              onClick={fetchBackendBreakdown} 
              disabled={loading || !vehicleId}
              size="sm"
            >
              {loading ? 'Loading...' : 'Calculate'}
            </Button>
          </div>
        )}

        {breakdown && (
          <>
            {/* Summary View */}
            <div className="space-y-3">
              {/* Hammer Price */}
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400">Winning Bid</span>
                <span className="font-semibold">{formatCurrency(breakdown.hammer_price)}</span>
              </div>

              {/* Buyer Premium */}
              <div className="flex justify-between items-center">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                      Buyer Premium ({breakdown.buyer_premium?.rate})
                      <HelpCircle className="h-3 w-3" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Fee charged to buyers for platform services.</p>
                      <p className="text-xs mt-1">Premium: 3.5% | VIP: 3%</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <span className="font-semibold">+ {formatCurrency(breakdown.buyer_premium?.amount)}</span>
              </div>

              {/* Platform Fee */}
              <div className="flex justify-between items-center">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                      Platform Fee ({breakdown.platform_fee?.rate})
                      <HelpCircle className="h-3 w-3" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{t("fees.transactionFeeDesc")}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <span className="font-semibold">+ {formatCurrency(breakdown.platform_fee?.amount)}</span>
              </div>

              <Separator />

              {/* Subtotal */}
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400">Subtotal (before tax)</span>
                <span className="font-semibold">{formatCurrency(breakdown.subtotal_before_tax)}</span>
              </div>

              {/* Taxes */}
              <div className="flex justify-between items-center">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                      Taxes ({breakdown.taxes?.type})
                      <HelpCircle className="h-3 w-3" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="space-y-1">
                        <p>Province: {province}</p>
                        {breakdown.taxes?.gst > 0 && <p>GST (5%): {formatCurrency(breakdown.taxes.gst)}</p>}
                        {breakdown.taxes?.pst > 0 && <p>PST: {formatCurrency(breakdown.taxes.pst)}</p>}
                        {breakdown.taxes?.qst > 0 && <p>QST (9.975%): {formatCurrency(breakdown.taxes.qst)}</p>}
                        {breakdown.taxes?.hst > 0 && <p>HST: {formatCurrency(breakdown.taxes.hst)}</p>}
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <span className="font-semibold">+ {formatCurrency(breakdown.taxes?.total)}</span>
              </div>

              <Separator className="border-2" />

              {/* Total */}
              <div className="flex justify-between items-center">
                <span className="font-bold text-lg">Total Payable</span>
                <span className="font-bold text-lg text-blue-600">
                  {formatCurrency(breakdown.total_payable)}
                </span>
              </div>

              {/* Subscription Badge */}
              <div className="flex items-center justify-between text-sm bg-slate-50 dark:bg-slate-800/50 rounded-lg p-2">
                <span className="text-slate-500">Your Rate</span>
                <Badge className={`${subscriptionTier === 'vip' ? 'bg-amber-100 text-amber-700' : subscriptionTier === 'premium' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                  {subscriptionTier === 'vip' ? 'VIP Elite (3%)' : subscriptionTier === 'premium' ? 'Premium (3.5%)' : 'Standard (5%)'}
                </Badge>
              </div>
            </div>

            {/* Expanded View with Savings */}
            {expanded && (
              <div className="space-y-4 pt-4 border-t">
                {/* Fee Tier Comparison */}
                <div>
                  <p className="text-sm font-medium mb-2">Buyer Premium by Tier</p>
                  <FeeTierComparison bidAmount={breakdown.hammer_price} type="buyer" />
                </div>

                {/* Savings Display */}
                {subscriptionTier !== 'vip' && (
                  <SavingsDisplay 
                    bidAmount={breakdown.hammer_price} 
                    currentTier={subscriptionTier} 
                  />
                )}

                {/* Payment Terms Notice */}
                <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <CreditCard className="h-5 w-5 text-amber-600 mt-0.5" />
                    <div className="text-sm">
                      <p className="font-medium text-amber-800 dark:text-amber-200">Payment Terms</p>
                      <p className="text-amber-700 dark:text-amber-300 mt-1">
                        Payment due within 14 days. Late payments subject to 2% monthly penalty.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

// Compact inline estimate (for bid panel)
export const PricingEstimateInline = ({ bidAmount, province, tier = 'free' }) => {
  if (!bidAmount || bidAmount <= 0) return null;

  const config = FEE_TIERS.buyer[tier] || FEE_TIERS.buyer.free;
  const taxConfig = TAX_RATES[province] || TAX_RATES.ON;
  
  const buyerPremium = (bidAmount * config.rate) / 100;
  const platformFee = (bidAmount * PLATFORM_FEE_RATE) / 100;
  const subtotal = bidAmount + buyerPremium + platformFee;
  const tax = (subtotal * taxConfig.rate) / 100;
  const total = subtotal + tax;

  return (
    <div className="text-xs text-slate-500 space-y-1" data-testid="pricing-estimate-inline">
      <div className="flex justify-between">
        <span>+ {config.rate}% buyer premium</span>
        <span>{formatCurrency(buyerPremium)}</span>
      </div>
      <div className="flex justify-between">
        <span>+ {taxConfig.type} ({taxConfig.rate}%)</span>
        <span>{formatCurrency(tax)}</span>
      </div>
      <div className="flex justify-between font-medium text-slate-700 dark:text-slate-300 pt-1 border-t">
        <span>Est. Total</span>
        <span>{formatCurrency(total)}</span>
      </div>
    </div>
  );
};

// Seller Commission Calculator
export const SellerCommissionCalculator = ({ salePrice, tier = 'free' }) => {
  if (!salePrice || salePrice <= 0) return null;

  const config = FEE_TIERS.seller[tier] || FEE_TIERS.seller.free;
  const commission = (salePrice * config.rate) / 100;
  const netPayout = salePrice - commission;

  return (
    <Card className="border-green-100 dark:border-green-900" data-testid="seller-commission-calculator">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Building2 className="h-5 w-5 text-green-600" />
          Seller Payout Estimate
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-slate-600 dark:text-slate-400">Sale Price</span>
          <span className="font-semibold">{formatCurrency(salePrice)}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-600 dark:text-slate-400">Commission ({config.rate}%)</span>
          <span className="font-semibold text-red-600">- {formatCurrency(commission)}</span>
        </div>
        <Separator />
        <div className="flex justify-between items-center">
          <span className="font-bold">Net Payout</span>
          <span className="font-bold text-green-600">{formatCurrency(netPayout)}</span>
        </div>
        
        <div className="flex items-center justify-between text-sm bg-slate-50 dark:bg-slate-800/50 rounded-lg p-2">
          <span className="text-slate-500">Your Rate</span>
          <Badge className={`${tier === 'vip' ? 'bg-amber-100 text-amber-700' : tier === 'premium' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
            {tier === 'vip' ? 'VIP Elite (2%)' : tier === 'premium' ? 'Premium (2.5%)' : 'Standard (4%)'}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
};

export default PricingCalculator;
