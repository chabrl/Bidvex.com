import API_BASE from '../../config';
/**
 * Vehicle Pricing Breakdown Component
 * Shows itemized fees, taxes, and totals for vehicle auctions
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { useTranslation } from 'react-i18next';
import {
  DollarSign, Percent, Receipt, Calculator, Info,
  ChevronDown, ChevronUp, Crown, Sparkles, AlertCircle
} from 'lucide-react';

const API = API_BASE;

// Format currency
const formatPrice = (amount) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
  }).format(amount || 0);
};

// Tier badge component
const TierBadge = ({ tier }) => {
  if (tier === 'vip_elite') {
    return (
      <Badge className="bg-gradient-to-r from-purple-500 to-pink-500 text-white">
        <Crown className="h-3 w-3 mr-1" /> VIP Elite
      </Badge>
    );
  }
  if (tier === 'premium') {
    return (
      <Badge className="bg-gradient-to-r from-blue-500 to-cyan-500 text-white">
        <Sparkles className="h-3 w-3 mr-1" /> Premium
      </Badge>
    );
  }
  return (
    <Badge variant="secondary">Basic</Badge>
  );
};

// Pricing breakdown component for before bidding
export const PricingEstimate = ({ vehicleId, bidAmount, province, listing = null }) => {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [breakdown, setBreakdown] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const fetchBreakdown = async () => {
      if (!bidAmount || bidAmount <= 0) return;
      
      setLoading(true);
      try {
        const response = await axios.post(
          `${API}/vehicles/${vehicleId}/pricing-breakdown`,
          null,
          {
            params: { bid_amount: bidAmount },
            headers: token ? { Authorization: `Bearer ${token}` } : {}
          }
        );
        setBreakdown(response.data.breakdown);
      } catch (error) {
        console.error('Failed to fetch pricing breakdown:', error);
      } finally {
        setLoading(false);
      }
    };

    const debounce = setTimeout(fetchBreakdown, 500);
    return () => clearTimeout(debounce);
  }, [vehicleId, bidAmount, token]);

  if (!breakdown && !loading) return null;

  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-sm font-medium text-slate-700 dark:text-slate-200"
      >
        <span className="flex items-center gap-2">
          <Calculator className="h-4 w-4" />
          Pricing Breakdown
        </span>
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {expanded && breakdown && (
        <div className="space-y-2 pt-2 border-t border-slate-200 dark:border-slate-700">
          {/* Hammer Price */}
          <div className="flex justify-between text-sm">
            <span className="text-slate-600 dark:text-slate-400">Hammer Price</span>
            <span className="font-medium">{formatPrice(breakdown.hammer_price)}</span>
          </div>

          {/* Buyer Premium */}
          <div className="flex justify-between text-sm">
            <span className="text-slate-600 dark:text-slate-400 flex items-center gap-1">
              Buyer Premium
              <span className="text-xs text-blue-600">({breakdown.buyer_premium?.rate})</span>
            </span>
            <span className="font-medium">{formatPrice(breakdown.buyer_premium?.amount)}</span>
          </div>

          {/* Platform Fee */}
          <div className="flex justify-between text-sm">
            <span className="text-slate-600 dark:text-slate-400 flex items-center gap-1">
              Platform Fee
              <span className="text-xs text-slate-500">({breakdown.platform_fee?.rate})</span>
            </span>
            <span className="font-medium">{formatPrice(breakdown.platform_fee?.amount)}</span>
          </div>

          {/* Subtotal */}
          <div className="flex justify-between text-sm pt-2 border-t border-dashed border-slate-300 dark:border-slate-600">
            <span className="text-slate-600 dark:text-slate-400">Subtotal</span>
            <span className="font-medium">{formatPrice(breakdown.subtotal_before_tax)}</span>
          </div>

          {/* Taxes */}
          <div className="bg-slate-100 dark:bg-slate-700/50 rounded p-2 space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600 dark:text-slate-400 flex items-center gap-1">
                Taxes ({breakdown.taxes?.province})
                <span className="text-xs">({breakdown.taxes?.rate})</span>
              </span>
              <span className="font-medium">{formatPrice(breakdown.taxes?.total)}</span>
            </div>
            {breakdown.taxes?.gst > 0 && (
              <div className="flex justify-between text-xs text-slate-500">
                <span>GST (5%)</span>
                <span>{formatPrice(breakdown.taxes.gst)}</span>
              </div>
            )}
            {breakdown.taxes?.pst > 0 && (
              <div className="flex justify-between text-xs text-slate-500">
                <span>PST</span>
                <span>{formatPrice(breakdown.taxes.pst)}</span>
              </div>
            )}
            {breakdown.taxes?.qst > 0 && (
              <div className="flex justify-between text-xs text-slate-500">
                <span>QST (9.975%)</span>
                <span>{formatPrice(breakdown.taxes.qst)}</span>
              </div>
            )}
            {breakdown.taxes?.hst > 0 && (
              <div className="flex justify-between text-xs text-slate-500">
                <span>HST</span>
                <span>{formatPrice(breakdown.taxes.hst)}</span>
              </div>
            )}
          </div>

          {/* Total */}
          <div className="flex justify-between text-base font-bold pt-2 border-t-2 border-slate-300 dark:border-slate-600">
            <span>{t("fees.totalPayable")}</span>
            <span className="text-blue-600 dark:text-blue-400">{formatPrice(breakdown.total_payable)}</span>
          </div>

          {/* Subscription Discount */}
          {breakdown.subscription_discount > 0 && (
            <div className="flex items-center justify-between bg-green-50 dark:bg-green-900/20 rounded p-2 text-sm">
              <span className="text-green-700 dark:text-green-400 flex items-center gap-1">
                <TierBadge tier={breakdown.subscription_tier} />
                Savings
              </span>
              <span className="text-green-600 font-medium">
                -{formatPrice(breakdown.subscription_discount)}
              </span>
            </div>
          )}

          {/* Payment Method Disclaimer */}
          {listing?.payment_method && listing.payment_method !== 'stripe' && (
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 rounded p-3 text-sm" data-testid="payment-method-disclaimer">
              <p className="font-medium text-amber-800 dark:text-amber-200">
                Seller accepts: {listing.payment_method === 'cash' ? 'Cash' : 'E-Transfer (Interac)'}
              </p>
              <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                BidVex facilitates the contract; payment is settled directly between buyer and seller.
              </p>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="text-center text-sm text-slate-500 py-2">
          Calculating...
        </div>
      )}
    </div>
  );
};

// Seller pricing info component
export const SellerPricingInfo = ({ subscriptionTier = 'basic' }) => {
  const commissionRates = {
    basic: '4%',
    premium: '2.5%',
    vip_elite: '2%'
  };

  const rate = commissionRates[subscriptionTier] || '4%';

  return (
    <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        <Percent className="h-5 w-5 text-amber-600" />
        <h4 className="font-semibold text-amber-800 dark:text-amber-200">Seller Commission</h4>
      </div>
      <p className="text-sm text-amber-700 dark:text-amber-300">
        Your commission rate: <span className="font-bold">{rate}</span>
      </p>
      <div className="mt-2 flex items-center gap-2">
        <TierBadge tier={subscriptionTier} />
        {subscriptionTier !== 'vip_elite' && (
          <span className="text-xs text-amber-600 dark:text-amber-400">
            Upgrade to save more!
          </span>
        )}
      </div>
    </div>
  );
};

// Full invoice view component
export const InvoiceView = ({ invoice }) => {
  const { t } = useTranslation();
  if (!invoice) return null;

  const isPaid = invoice.payment_status === 'paid';
  const isOverdue = invoice.payment_status === 'overdue';

  return (
    <Card className="overflow-hidden">
      <CardHeader className={`${
        isPaid ? 'bg-green-600' : isOverdue ? 'bg-red-600' : 'bg-blue-600'
      } text-white`}>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Receipt className="h-5 w-5" />
              Invoice #{invoice.invoice_number}
            </CardTitle>
            <p className="text-sm opacity-90 mt-1">
              {invoice.vehicle_title}
            </p>
          </div>
          <Badge className={`${
            isPaid ? 'bg-white text-green-600' : 
            isOverdue ? 'bg-white text-red-600' : 
            'bg-white/20 text-white'
          }`}>
            {invoice.payment_status?.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-6 space-y-4">
        {/* Line Items */}
        <div className="space-y-2">
          {invoice.line_items?.map((item, index) => (
            <div key={index} className="flex justify-between text-sm">
              <span className="text-slate-600 dark:text-slate-400">
                {item.description}
                {item.rate && <span className="text-xs ml-1">({(item.rate * 100).toFixed(1)}%)</span>}
              </span>
              <span className={`font-medium ${item.amount < 0 ? 'text-red-600' : ''}`}>
                {item.amount < 0 ? '-' : ''}{formatPrice(Math.abs(item.amount))}
              </span>
            </div>
          ))}
        </div>

        {/* Totals */}
        <div className="pt-4 border-t border-slate-200 dark:border-slate-700 space-y-2">
          <div className="flex justify-between">
            <span className="text-slate-600">Subtotal</span>
            <span className="font-medium">{formatPrice(invoice.subtotal_before_tax)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-600">
              Taxes ({invoice.tax_type})
            </span>
            <span className="font-medium">{formatPrice(invoice.tax_total)}</span>
          </div>
          {invoice.deposit_credited > 0 && (
            <div className="flex justify-between text-green-600">
              <span>{t("fees.depositCredit")}</span>
              <span>-{formatPrice(invoice.deposit_credited)}</span>
            </div>
          )}
          {invoice.penalty_amount > 0 && (
            <div className="flex justify-between text-red-600">
              <span className="flex items-center gap-1">
                <AlertCircle className="h-4 w-4" />
                Late Penalty
              </span>
              <span>+{formatPrice(invoice.penalty_amount)}</span>
            </div>
          )}
        </div>

        {/* Total Due */}
        <div className="flex justify-between text-lg font-bold pt-4 border-t-2">
          <span>{isPaid ? 'Total Paid' : 'Total Due'}</span>
          <span className={isPaid ? 'text-green-600' : isOverdue ? 'text-red-600' : 'text-blue-600'}>
            {formatPrice(invoice.amount_due || invoice.total_amount)}
          </span>
        </div>

        {/* Payment Deadline */}
        {!isPaid && invoice.time_status && (
          <div className={`p-3 rounded-lg ${
            isOverdue 
              ? 'bg-red-50 border border-red-200 text-red-700' 
              : 'bg-amber-50 border border-amber-200 text-amber-700'
          }`}>
            <p className="text-sm font-medium">
              {isOverdue 
                ? `⚠️ ${invoice.time_status.message}` 
                : `⏰ Payment due: ${invoice.time_status.message}`}
            </p>
          </div>
        )}

        {/* Pay Button */}
        {!isPaid && (
          <Button className="w-full" size="lg">
            <DollarSign className="h-5 w-5 mr-2" />
            Pay Now
          </Button>
        )}

        {/* Subscription Info */}
        {invoice.subscription_discount > 0 && (
          <div className="flex items-center justify-between bg-green-50 dark:bg-green-900/20 rounded p-3 text-sm">
            <span className="text-green-700 dark:text-green-400 flex items-center gap-2">
              <TierBadge tier={invoice.subscription_tier} />
              Member Savings
            </span>
            <span className="text-green-600 font-bold">
              {formatPrice(invoice.subscription_discount)}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default { PricingEstimate, SellerPricingInfo, InvoiceView };
