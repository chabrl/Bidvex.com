import API_BASE from '../config';
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Package, Layers, ArrowRight, Lock, AlertTriangle, CreditCard, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

const API = API_BASE;

/**
 * SellOptionsModal Component
 * Displays modal with two listing type options:
 * 1. Create Single Item Listing
 * 2. Create Multi-Item Auction
 * 
 * Partner accounts with unpaid fees see a lockdown banner instead.
 */
const SellOptionsModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const { canCreateMultiLot } = useFeatureFlags();
  const [paymentLoading, setPaymentLoading] = useState(false);

  const isPartnerLocked = user?.is_partner && !user?.platform_fee_paid;

  const handleSelectOption = (path) => {
    if (isPartnerLocked) {
      toast.error('Please complete your annual partner fee payment first.');
      return;
    }
    if (path === '/create-multi-item-listing' && !canCreateMultiLot(user)) {
      toast.error('Multi-lot auctions are restricted to business accounts. Please upgrade your account.');
      return;
    }
    onClose();
    navigate(path);
  };

  const handlePayPartnerFee = async () => {
    setPaymentLoading(true);
    try {
      const res = await axios.post(`${API}/partner/create-checkout`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      } else {
        toast.error('Unable to create payment session. Please contact support.');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create payment session.');
    } finally {
      setPaymentLoading(false);
    }
  };
  
  const canAccessMultiLot = canCreateMultiLot(user);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl max-w-[calc(100vw-1.5rem)] p-4 sm:p-6 max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl sm:text-2xl font-bold">Choose Listing Type</DialogTitle>
          <DialogDescription className="text-xs sm:text-sm">
            Select the type of auction you want to create
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4 mt-3 sm:mt-4">
          {/* Partner Fee Lockdown Banner */}
          {isPartnerLocked && (
            <div className="md:col-span-2 rounded-lg border border-amber-200 bg-amber-50 p-5" data-testid="partner-fee-lockdown-banner">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <h3 className="font-semibold text-amber-900 text-sm">Annual Partner Fee Required</h3>
                  <p className="text-sm text-amber-700 mt-1">
                    Your partner application has been approved, but your annual fee of <strong>$100 CAD/year + taxes</strong> is required to activate listing capabilities.
                  </p>
                  <Button
                    onClick={handlePayPartnerFee}
                    disabled={paymentLoading}
                    className="mt-3 bg-amber-600 hover:bg-amber-700 text-white"
                    size="sm"
                    data-testid="partner-pay-fee-btn"
                  >
                    {paymentLoading ? (
                      <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Processing...</>
                    ) : (
                      <><CreditCard className="h-4 w-4 mr-1.5" /> Pay Annual Fee &rarr;</>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Single Item Listing Option */}
          <Card 
            className={`transition-all duration-200 border-2 ${
              isPartnerLocked 
                ? 'opacity-50 cursor-not-allowed bg-gray-50' 
                : 'cursor-pointer hover:shadow-lg hover:border-primary'
            }`}
            onClick={() => handleSelectOption('/create-listing')}
            data-testid="sell-option-single"
          >
            <CardContent className="p-4 sm:p-6">
              <div className="flex flex-col items-center text-center space-y-3 sm:space-y-4">
                <div className="p-3 sm:p-4 bg-primary/10 rounded-full">
                  <Package className="h-9 w-9 sm:h-12 sm:w-12 text-primary" />
                </div>
                <h3 className="text-lg sm:text-xl font-semibold">Single Item Listing</h3>
                <p className="text-xs sm:text-sm text-muted-foreground">
                  Perfect for selling individual items or single products
                </p>
                <ul className="text-xs sm:text-sm text-left space-y-1.5 sm:space-y-2 w-full">
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-primary flex-shrink-0" />
                    One item per auction
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-primary flex-shrink-0" />
                    Simple setup process
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-primary flex-shrink-0" />
                    Quick to create
                  </li>
                </ul>
                <Button className="w-full gradient-button text-white border-0" data-testid="single-listing-cta">
                  Create Single Listing
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Multi-Item Auction Option */}
          <Card 
            className="transition-all duration-200 border-2 cursor-pointer hover:shadow-lg hover:border-primary"
            onClick={() => handleSelectOption('/create-multi-item-listing')}
            data-testid="sell-option-multi"
          >
            <CardContent className="p-4 sm:p-6">
              <div className="flex flex-col items-center text-center space-y-3 sm:space-y-4">
                <div className="p-3 sm:p-4 rounded-full bg-purple-500/10">
                  <Layers className="h-9 w-9 sm:h-12 sm:w-12 text-purple-600" />
                </div>
                <h3 className="text-lg sm:text-xl font-semibold">Multi-Item Auction</h3>
                <p className="text-xs sm:text-sm text-muted-foreground">
                  Ideal for bulk sales, liquidations, or multiple related items
                </p>
                <ul className="text-xs sm:text-sm text-left space-y-1.5 sm:space-y-2 w-full">
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-purple-600 flex-shrink-0" />
                    Multiple lots in one auction
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-purple-600 flex-shrink-0" />
                    Staggered bidding (1-min intervals)
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-purple-600 flex-shrink-0" />
                    Higher visibility
                  </li>
                </ul>
                <Button 
                  className="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white border-0 hover:opacity-90"
                  data-testid="multi-listing-cta"
                >
                  Create Multi-Item Auction
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SellOptionsModal;
