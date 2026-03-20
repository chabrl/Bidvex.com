import React, { useState } from 'react';
import { Button } from './ui/button';
import { ShoppingCart, AlertCircle, CheckCircle2, Loader2, CreditCard } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { formatCurrency } from '../utils/currencyFormatter';
import { useTranslation } from 'react-i18next';
import { Separator } from './ui/separator';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const BuyNowButton = ({ lot, auctionId, onPurchaseComplete }) => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [showModal, setShowModal] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState(null);

  const availableQty = lot.available_quantity || lot.quantity || 1;
  const buyNowPrice = lot.buy_now_price;

  const fetchPreview = async (qty) => {
    setPreviewLoading(true);
    try {
      const res = await axios.post(
        `${API_URL}/api/payments/buy-now-preview`,
        { auction_id: auctionId, lot_number: lot.lot_number, quantity: qty },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      setPreview(res.data);
    } catch (err) {
      console.error('Preview error:', err);
      toast.error(err.response?.data?.detail || 'Failed to load price breakdown');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleOpenModal = async () => {
    if (!user) {
      toast.error('Please log in to purchase');
      window.location.href = '/auth';
      return;
    }
    setShowModal(true);
    setQuantity(1);
    await fetchPreview(1);
  };

  const handleQuantityChange = async (newQty) => {
    const clamped = Math.min(availableQty, Math.max(1, newQty));
    setQuantity(clamped);
    await fetchPreview(clamped);
  };

  const handleConfirmAndPay = async () => {
    if (quantity > availableQty) {
      toast.error(`Only ${availableQty} units available`);
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(
        `${API_URL}/api/payments/buy-now-checkout`,
        {
          auction_id: auctionId,
          lot_number: lot.lot_number,
          quantity: quantity,
          return_url: `${window.location.origin}/marketplace`,
        },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );

      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      } else {
        toast.error('Failed to create checkout session');
        setLoading(false);
      }
    } catch (error) {
      console.error('Buy Now checkout error:', error);
      toast.error(
        error.response?.data?.detail || 'Purchase failed. Please try again.',
        { duration: 5000 }
      );
      setLoading(false);
    }
  };

  if (!lot.buy_now_enabled || !buyNowPrice) return null;

  if (availableQty <= 0) {
    return (
      <div className="text-sm text-red-600 font-medium" data-testid="buy-now-sold-out">
        Sold Out
      </div>
    );
  }

  return (
    <>
      <Button
        onClick={handleOpenModal}
        className="w-full bg-green-600 hover:bg-green-700 text-white border-0"
        disabled={availableQty <= 0}
        data-testid="buy-now-open-btn"
      >
        <ShoppingCart className="h-4 w-4 mr-2" />
        Buy Now - {formatCurrency(buyNowPrice)}
      </Button>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-900 rounded-lg max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in duration-200">
            {/* Header */}
            <div className="flex items-start gap-3">
              <div className="h-12 w-12 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0">
                <ShoppingCart className="h-6 w-6 text-green-600 dark:text-green-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Confirm Purchase
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {lot.title}
                </p>
              </div>
            </div>

            {/* Item Details */}
            <div className="bg-gray-50 dark:bg-slate-800 rounded-lg p-4 space-y-3 border border-gray-200 dark:border-slate-700">
              {lot.images && lot.images[0] && (
                <img src={lot.images[0]} alt={lot.title} className="w-full h-32 object-cover rounded" />
              )}

              {/* Quantity Selector */}
              {availableQty > 1 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Quantity:</label>
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline" size="sm"
                      onClick={() => handleQuantityChange(quantity - 1)}
                      disabled={quantity <= 1 || previewLoading}
                    >-</Button>
                    <input
                      type="number" min="1" max={availableQty} value={quantity}
                      onChange={(e) => handleQuantityChange(parseInt(e.target.value) || 1)}
                      className="w-20 text-center border rounded px-2 py-1 dark:bg-slate-700 dark:border-slate-600"
                      data-testid="buy-now-quantity-input"
                    />
                    <Button
                      variant="outline" size="sm"
                      onClick={() => handleQuantityChange(quantity + 1)}
                      disabled={quantity >= availableQty || previewLoading}
                    >+</Button>
                    <span className="text-sm text-gray-600 dark:text-gray-400">(Max: {availableQty})</span>
                  </div>
                </div>
              )}
            </div>

            {/* Price Breakdown */}
            {previewLoading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-5 w-5 animate-spin text-primary mr-2" />
                <span className="text-sm text-gray-500">Calculating...</span>
              </div>
            ) : preview ? (
              <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-4 space-y-2 text-sm" data-testid="buy-now-breakdown">
                <div className="flex justify-between">
                  <span className="text-gray-700 dark:text-gray-300">
                    Item Price ({quantity > 1 ? `${formatCurrency(preview.price_per_unit)} x ${quantity}` : ''})
                  </span>
                  <span className="font-medium">{formatCurrency(preview.item_total)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">
                    Buyer's Premium ({(preview.buyer_premium_rate * 100).toFixed(1)}%)
                  </span>
                  <span>{formatCurrency(preview.buyer_premium)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Taxes (GST/QST)</span>
                  <span>{formatCurrency(preview.total_tax)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Processing Fee</span>
                  <span>{formatCurrency(preview.processing_fee)}</span>
                </div>
                <Separator />
                <div className="flex justify-between items-center pt-1">
                  <span className="font-bold text-gray-900 dark:text-white">Total Due</span>
                  <span className="text-xl font-bold text-green-600 dark:text-green-400" data-testid="buy-now-total">
                    {formatCurrency(preview.buyer_total)}
                  </span>
                </div>
              </div>
            ) : null}

            {/* Info Note */}
            <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-800 dark:text-amber-300">
                  You will be redirected to Stripe's secure checkout to complete payment.
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => { setShowModal(false); setQuantity(1); setPreview(null); }}
                disabled={loading}
                className="flex-1"
                data-testid="buy-now-cancel-btn"
              >
                Cancel
              </Button>
              <Button
                onClick={handleConfirmAndPay}
                disabled={loading || previewLoading || !preview}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white border-0"
                data-testid="buy-now-confirm-btn"
              >
                {loading ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Redirecting...</>
                ) : (
                  <><CreditCard className="h-4 w-4 mr-2" />Confirm & Pay</>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default BuyNowButton;
