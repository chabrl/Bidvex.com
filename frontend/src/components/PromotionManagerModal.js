import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { toast } from 'sonner';
import axios from 'axios';
import { Loader2, TrendingUp, Target, Calendar, DollarSign, MapPin, Users } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PROMOTION_TIERS = [
  {
    type: 'basic',
    name: 'Basic Promotion',
    price: 9.99,
    duration: 7,
    features: ['Featured badge', 'Top of category', '7 days visibility'],
  },
  {
    type: 'standard',
    name: 'Standard Promotion',
    price: 24.99,
    duration: 14,
    features: ['Featured badge', 'Top of category', 'Homepage feature', '14 days visibility'],
  },
  {
    type: 'premium',
    name: 'Premium Promotion',
    price: 49.99,
    duration: 30,
    features: ['Featured badge', 'Top of category', 'Homepage feature', 'Email blast', '30 days visibility'],
  },
];

const PromotionManagerModal = ({ open, onClose, listingId, listingTitle }) => {
  const [loading, setLoading] = useState(false);
  const [selectedTier, setSelectedTier] = useState(null);
  const [targeting, setTargeting] = useState({
    location: '',
    ageRange: '',
    interests: '',
  });

  const handlePromote = async () => {
    if (!selectedTier) {
      toast.error('Please select a promotion tier');
      return;
    }

    setLoading(true);

    try {
      // Calculate end date based on tier duration
      const endDate = new Date();
      endDate.setDate(endDate.getDate() + selectedTier.duration);

      const promotionData = {
        listing_id: listingId,
        promotion_type: selectedTier.type,
        price: selectedTier.price,
        end_date: endDate.toISOString(),
        targeting: {
          location: targeting.location || 'all',
          ageRange: targeting.ageRange || 'all',
          interests: targeting.interests || 'all',
        },
      };

      // Create promotion in backend
      const promotionResponse = await axios.post(`${API}/promotions`, promotionData);

      // Initiate Stripe payment
      const paymentResponse = await axios.post(`${API}/payments/promote`, {
        promotion_id: promotionResponse.data.id,
        amount: selectedTier.price,
        origin_url: window.location.origin,
      });

      // Redirect to Stripe checkout
      window.location.href = paymentResponse.data.url;
    } catch (error) {
      console.error('Failed to create promotion:', error);
      toast.error(error.response?.data?.detail || 'Failed to create promotion');
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold gradient-text">
            Promote Your Listing
          </DialogTitle>
          <p className="text-muted-foreground">
            Boost visibility for: <span className="font-semibold">{listingTitle}</span>
          </p>
        </DialogHeader>

        <div className="space-y-6">
          {/* Promotion Tiers */}
          <div>
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              Choose Promotion Tier
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {PROMOTION_TIERS.map((tier) => (
                <Card
                  key={tier.type}
                  className={`cursor-pointer transition-all hover:shadow-lg ${
                    selectedTier?.type === tier.type
                      ? 'ring-2 ring-primary shadow-lg'
                      : 'hover:ring-1 hover:ring-gray-300'
                  }`}
                  onClick={() => setSelectedTier(tier)}
                >
                  <CardContent className="p-6">
                    <div className="text-center mb-4">
                      <h4 className="text-xl font-bold mb-2">{tier.name}</h4>
                      <div className="text-3xl font-bold gradient-text mb-1">
                        ${tier.price}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {tier.duration} days
                      </p>
                    </div>
                    <Separator className="my-4" />
                    <ul className="space-y-2">
                      {tier.features.map((feature, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-sm">
                          <span className="text-green-500">✓</span>
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {selectedTier && (
            <>
              {/* Targeting Options */}
              <div>
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Target className="h-5 w-5 text-primary" />
                  Targeting Options (Optional)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="location" className="flex items-center gap-2">
                      <MapPin className="h-4 w-4" />
                      Location
                    </Label>
                    <Input
                      id="location"
                      placeholder="e.g., New York, California"
                      value={targeting.location}
                      onChange={(e) =>
                        setTargeting({ ...targeting, location: e.target.value })
                      }
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="ageRange" className="flex items-center gap-2">
                      <Users className="h-4 w-4" />
                      Age Range
                    </Label>
                    <select
                      id="ageRange"
                      value={targeting.ageRange}
                      onChange={(e) =>
                        setTargeting({ ...targeting, ageRange: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-input rounded-md bg-background"
                    >
                      <option value="">All Ages</option>
                      <option value="18-24">18-24</option>
                      <option value="25-34">25-34</option>
                      <option value="35-44">35-44</option>
                      <option value="45-54">45-54</option>
                      <option value="55+">55+</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="interests">Interests</Label>
                    <Input
                      id="interests"
                      placeholder="e.g., Technology, Fashion"
                      value={targeting.interests}
                      onChange={(e) =>
                        setTargeting({ ...targeting, interests: e.target.value })
                      }
                    />
                  </div>
                </div>
              </div>

              {/* Preview */}
              <div className="bg-gradient-to-br from-primary/10 to-accent/10 p-6 rounded-lg">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-primary" />
                  Promotion Preview
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Promotion Type:</span>
                    <Badge className="gradient-bg text-white border-0">
                      {selectedTier.name}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Duration:</span>
                    <span className="font-semibold">{selectedTier.duration} days</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Price:</span>
                    <span className="text-2xl font-bold gradient-text">
                      ${selectedTier.price}
                    </span>
                  </div>
                  {targeting.location && (
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Target Location:</span>
                      <span className="font-medium">{targeting.location}</span>
                    </div>
                  )}
                  {targeting.ageRange && (
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Target Age:</span>
                      <span className="font-medium">{targeting.ageRange}</span>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 justify-end">
            <Button variant="outline" onClick={onClose} disabled={loading}>
              Cancel
            </Button>
            <Button
              className="gradient-button text-white border-0"
              onClick={handlePromote}
              disabled={!selectedTier || loading}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <DollarSign className="mr-2 h-4 w-4" />
                  Proceed to Payment
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default PromotionManagerModal;
