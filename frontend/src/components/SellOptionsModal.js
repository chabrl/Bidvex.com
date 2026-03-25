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

const API = `${API_BASE}/api`;

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
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold">Choose Listing Type</DialogTitle>
          <DialogDescription>
            Select the type of auction you want to create
          </DialogDescription>
        </DialogHeader>

        <div className="grid md:grid-cols-2 gap-4 mt-4">
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
                : 'cursor-pointer hover:shadow-lg hover:scale-105 hover:border-primary'
            }`}
            onClick={() => handleSelectOption('/create-listing')}
            data-testid="sell-option-single"
          >
            <CardContent className="p-6">
              <div className="flex flex-col items-center text-center space-y-4">
                <div className="p-4 bg-primary/10 rounded-full">
                  <Package className="h-12 w-12 text-primary" />
                </div>
                <h3 className="text-xl font-semibold">Single Item Listing</h3>
                <p className="text-sm text-muted-foreground">
                  Perfect for selling individual items or single products
                </p>
                <ul className="text-sm text-left space-y-2 w-full">
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-primary" />
                    One item per auction
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-primary" />
                    Simple setup process
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-primary" />
                    Quick to create
                  </li>
                </ul>
                <Button className="w-full gradient-button text-white border-0">
                  Create Single Listing
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Multi-Item Auction Option */}
          <Card 
            className={`transition-all duration-200 border-2 ${
              canAccessMultiLot 
                ? 'cursor-pointer hover:shadow-lg hover:scale-105 hover:border-primary' 
                : 'opacity-75 cursor-not-allowed bg-gray-50'
            }`}
            onClick={() => handleSelectOption('/create-multi-item-listing')}
          >
            <CardContent className="p-6">
              <div className="flex flex-col items-center text-center space-y-4">
                <div className={`p-4 rounded-full ${canAccessMultiLot ? 'bg-purple-500/10' : 'bg-gray-200'}`}>
                  {canAccessMultiLot ? (
                    <Layers className="h-12 w-12 text-purple-600" />
                  ) : (
                    <Lock className="h-12 w-12 text-gray-400" />
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <h3 className="text-xl font-semibold">Multi-Item Auction</h3>
                  {!canAccessMultiLot && (
                    <Badge variant="secondary" className="bg-amber-100 text-amber-700">
                      Business Only
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">
                  Ideal for bulk sales, liquidations, or multiple related items
                </p>
                <ul className="text-sm text-left space-y-2 w-full">
                  <li className="flex items-center gap-2">
                    <ArrowRight className={`h-4 w-4 ${canAccessMultiLot ? 'text-purple-600' : 'text-gray-400'}`} />
                    Multiple lots in one auction
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className={`h-4 w-4 ${canAccessMultiLot ? 'text-purple-600' : 'text-gray-400'}`} />
                    Staggered bidding (1-min intervals)
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className={`h-4 w-4 ${canAccessMultiLot ? 'text-purple-600' : 'text-gray-400'}`} />
                    Higher visibility
                  </li>
                </ul>
                <Button 
                  className={`w-full ${
                    canAccessMultiLot 
                      ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white border-0 hover:opacity-90' 
                      : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  }`}
                  disabled={!canAccessMultiLot}
                >
                  {canAccessMultiLot ? 'Create Multi-Item Auction' : 'Upgrade to Business Account'}
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
