import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Package, Layers, ArrowRight, Lock } from 'lucide-react';
import { toast } from 'sonner';

/**
 * SellOptionsModal Component
 * Displays modal with two listing type options:
 * 1. Create Single Item Listing
 * 2. Create Multi-Item Auction
 * 
 * Multi-Item Auction visibility is controlled by:
 * - User has business account, OR
 * - Admin has enabled allow_all_users_multi_lot flag
 */
const SellOptionsModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { canCreateMultiLot } = useFeatureFlags();

  const handleSelectOption = (path) => {
    if (path === '/create-multi-item-listing' && !canCreateMultiLot(user)) {
      toast.error('Multi-lot auctions are restricted to business accounts. Please upgrade your account.');
      return;
    }
    onClose();
    navigate(path);
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
          {/* Single Item Listing Option */}
          <Card 
            className="cursor-pointer hover:shadow-lg transition-all duration-200 hover:scale-105 border-2 hover:border-primary"
            onClick={() => handleSelectOption('/create-listing')}
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
            className="cursor-pointer hover:shadow-lg transition-all duration-200 hover:scale-105 border-2 hover:border-primary"
            onClick={() => handleSelectOption('/create-multi-item-listing')}
          >
            <CardContent className="p-6">
              <div className="flex flex-col items-center text-center space-y-4">
                <div className="p-4 bg-purple-500/10 rounded-full">
                  <Layers className="h-12 w-12 text-purple-600" />
                </div>
                <h3 className="text-xl font-semibold">Multi-Item Auction</h3>
                <p className="text-sm text-muted-foreground">
                  Ideal for bulk sales, liquidations, or multiple related items
                </p>
                <ul className="text-sm text-left space-y-2 w-full">
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-purple-600" />
                    Multiple lots in one auction
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-purple-600" />
                    Staggered bidding (1-min intervals)
                  </li>
                  <li className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4 text-purple-600" />
                    Higher visibility
                  </li>
                </ul>
                <Button className="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white border-0 hover:opacity-90">
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
