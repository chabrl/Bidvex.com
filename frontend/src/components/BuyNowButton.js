import React, { useState } from 'react';
import { Button } from './ui/button';
import { ShoppingCart, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

/**
 * Buy Now button with confirmation modal and quantity selection
 * Implements atomic quantity decrement for partial lot liquidation
 */
const BuyNowButton = ({ lot, auctionId, onPurchaseComplete }) => {
  const { user } = useAuth();
  const [showModal, setShowModal] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(false);

  const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  const availableQty = lot.available_quantity || lot.quantity || 1;
  const buyNowPrice = lot.buy_now_price;
  const totalAmount = buyNowPrice * quantity;

  const handleBuyNow = async () => {
    if (!user) {
      toast.error('Please log in to purchase');
      window.location.href = '/auth';
      return;
    }

    if (quantity > availableQty) {
      toast.error(`Only ${availableQty} units available`);
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post(
        `${API_URL}/api/buy-now`,
        {
          auction_id: auctionId,
          lot_number: lot.lot_number,
          quantity: quantity
        },
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`
          }
        }
      );

      if (response.data.success) {
        toast.success(
          `Purchase successful! ${quantity} unit(s) for $${totalAmount.toFixed(2)}`,
          {
            description: 'Payment pending. Check your dashboard for details.',
            duration: 7000
          }
        );

        setShowModal(false);
        setQuantity(1);

        if (onPurchaseComplete) {
          onPurchaseComplete(response.data);
        }
      }
    } catch (error) {
      console.error('Buy Now error:', error);
      toast.error(
        error.response?.data?.detail ||
        'Purchase failed. Please try again.',
        {
          description: error.response?.data?.message,
          duration: 5000
        }
      );
    } finally {
      setLoading(false);
    }
  };

  if (!lot.buy_now_enabled || !buyNowPrice) {
    return null;
  }

  if (availableQty <= 0) {
    return (
      <div className="text-sm text-red-600 font-medium">
        ❌ Sold Out
      </div>
    );
  }

  return (
    <>
      <Button
        onClick={() => setShowModal(true)}
        className="w-full bg-green-600 hover:bg-green-700 text-white border-0"
        disabled={availableQty <= 0}
      >
        <ShoppingCart className="h-4 w-4 mr-2" />
        Buy Now - ${buyNowPrice.toFixed(2)}
      </Button>

      {/* Confirmation Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in duration-200">
            <div className="flex items-start gap-3">
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                <ShoppingCart className="h-6 w-6 text-green-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-gray-900">
                  Confirm Purchase
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  Buy {lot.title} at the fixed price
                </p>
              </div>
            </div>

            {/* Item Details */}
            <div className="bg-gray-50 rounded-lg p-4 space-y-3 border-2 border-gray-200">
              {lot.images && lot.images[0] && (
                <img
                  src={lot.images[0]}
                  alt={lot.title}
                  className="w-full h-32 object-cover rounded"
                />
              )}

              <div>
                <h4 className="font-semibold text-gray-900">{lot.title}</h4>
                <p className="text-sm text-gray-600 line-clamp-2">
                  {lot.description}
                </p>
              </div>

              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Available:</span>
                <span className="font-semibold">{availableQty} units</span>
              </div>

              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Buy Now Price:</span>
                <span className="font-semibold">${buyNowPrice.toFixed(2)} per unit</span>
              </div>

              {/* Quantity Selector */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">
                  Quantity to Purchase:
                </label>
                <div className="flex items-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setQuantity(Math.max(1, quantity - 1))}
                    disabled={quantity <= 1}
                  >
                    -
                  </Button>
                  <input
                    type="number"
                    min="1"
                    max={availableQty}
                    value={quantity}
                    onChange={(e) => {
                      const val = parseInt(e.target.value) || 1;
                      setQuantity(Math.min(availableQty, Math.max(1, val)));
                    }}
                    className="w-20 text-center border rounded px-2 py-1"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setQuantity(Math.min(availableQty, quantity + 1))}
                    disabled={quantity >= availableQty}
                  >
                    +
                  </Button>
                  <span className="text-sm text-gray-600">
                    (Max: {availableQty})
                  </span>
                </div>
              </div>

              <div className="border-t pt-3 mt-3">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-gray-900">Total Amount:</span>
                  <span className="text-2xl font-bold text-green-600">
                    ${totalAmount.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            {/* Important Note */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-blue-800">
                  <p className="font-semibold mb-1">Instant Purchase</p>
                  <p>
                    This is a <strong>Buy Now</strong> purchase. You will immediately secure {quantity} unit(s) at the fixed price of ${buyNowPrice.toFixed(2)} per unit. 
                    {quantity < availableQty && (
                      <span className="block mt-1">
                        The auction will continue for the remaining {availableQty - quantity} unit(s).
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => {
                  setShowModal(false);
                  setQuantity(1);
                }}
                disabled={loading}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleBuyNow}
                disabled={loading}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white border-0"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    Confirm Purchase
                  </>
                )}
              </Button>
            </div>

            <p className="text-xs text-center text-gray-500">
              Payment will be processed after confirmation
            </p>
          </div>
        </div>
      )}
    </>
  );
};

export default BuyNowButton;
