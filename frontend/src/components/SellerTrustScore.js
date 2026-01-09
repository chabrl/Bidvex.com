import React, { useState, useEffect } from 'react';
import { Star, Shield, CheckCircle, Clock, Package, MessageSquare, Award } from 'lucide-react';
import { Badge } from './ui/badge';
import { Card, CardContent } from './ui/card';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * SellerTrustScore - Displays seller trust rating and badges
 * 
 * Trust Score is calculated from:
 * - Automated metrics (pickup speed, payment completion)
 * - Buyer ratings (1-5 stars post-transaction)
 * 
 * Display:
 * - Star rating (1-5)
 * - "Trusted Seller" badge for scores >= 4.5
 * - Breakdown by category
 */

const TrustBadge = ({ score }) => {
  if (score >= 4.5) {
    return (
      <Badge 
        className="bg-gradient-to-r from-emerald-500 to-green-600 text-white font-bold px-3 py-1.5 shadow-lg"
        data-testid="trusted-seller-badge"
      >
        <Shield className="h-4 w-4 mr-1.5" />
        BidVex Trusted Seller
      </Badge>
    );
  }
  return null;
};

const StarRating = ({ rating, size = 'default' }) => {
  const stars = [];
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;
  
  const starSize = size === 'small' ? 'h-4 w-4' : 'h-5 w-5';
  
  for (let i = 0; i < 5; i++) {
    if (i < fullStars) {
      stars.push(
        <Star 
          key={i} 
          className={`${starSize} fill-amber-400 text-amber-400`}
        />
      );
    } else if (i === fullStars && hasHalfStar) {
      stars.push(
        <div key={i} className="relative">
          <Star className={`${starSize} text-slate-300`} />
          <div className="absolute inset-0 overflow-hidden w-1/2">
            <Star className={`${starSize} fill-amber-400 text-amber-400`} />
          </div>
        </div>
      );
    } else {
      stars.push(
        <Star key={i} className={`${starSize} text-slate-300`} />
      );
    }
  }
  
  return <div className="flex items-center gap-0.5" data-testid="star-rating">{stars}</div>;
};

const TrustScoreDisplay = ({ sellerId, variant = 'full', showBadge = true }) => {
  const [trustData, setTrustData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrustScore = async () => {
      try {
        const response = await axios.get(`${API}/sellers/${sellerId}/trust-score`);
        setTrustData(response.data);
      } catch (error) {
        console.log('Trust score not available');
        // Set default data
        setTrustData({
          overall_score: 0,
          total_ratings: 0,
          metrics: {
            pickup_speed: 0,
            item_accuracy: 0,
            communication: 0
          }
        });
      } finally {
        setLoading(false);
      }
    };

    if (sellerId) {
      fetchTrustScore();
    }
  }, [sellerId]);

  if (loading) {
    return (
      <div className="animate-pulse flex items-center gap-2">
        <div className="h-5 w-24 bg-slate-200 rounded" />
      </div>
    );
  }

  if (!trustData || trustData.total_ratings === 0) {
    return (
      <div className="flex items-center gap-2 text-slate-500">
        <Star className="h-4 w-4" />
        <span className="text-sm">New Seller - No ratings yet</span>
      </div>
    );
  }

  // Compact variant - just stars and score
  if (variant === 'compact') {
    return (
      <div className="flex items-center gap-2" data-testid="trust-score-compact">
        <StarRating rating={trustData.overall_score} size="small" />
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          {trustData.overall_score.toFixed(1)}
        </span>
        <span className="text-xs text-slate-500">
          ({trustData.total_ratings})
        </span>
        {showBadge && <TrustBadge score={trustData.overall_score} />}
      </div>
    );
  }

  // Full variant - detailed breakdown
  return (
    <Card className="border-2 border-slate-200 dark:border-slate-700" data-testid="trust-score-full">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg">
              <Award className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <h4 className="font-semibold text-slate-900 dark:text-white">Seller Trust Score</h4>
              <p className="text-sm text-slate-500">{trustData.total_ratings} verified ratings</p>
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2">
              <StarRating rating={trustData.overall_score} />
              <span className="text-2xl font-bold text-slate-900 dark:text-white">
                {trustData.overall_score.toFixed(1)}
              </span>
            </div>
            {showBadge && <TrustBadge score={trustData.overall_score} />}
          </div>
        </div>

        {/* Metrics Breakdown */}
        <div className="grid grid-cols-3 gap-3">
          <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg text-center">
            <Clock className="h-5 w-5 mx-auto mb-1 text-blue-600" />
            <p className="text-xs text-slate-500 mb-1">Pickup Speed</p>
            <p className="font-bold text-slate-900 dark:text-white">
              {trustData.metrics?.pickup_speed?.toFixed(1) || 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg text-center">
            <Package className="h-5 w-5 mx-auto mb-1 text-green-600" />
            <p className="text-xs text-slate-500 mb-1">Item Accuracy</p>
            <p className="font-bold text-slate-900 dark:text-white">
              {trustData.metrics?.item_accuracy?.toFixed(1) || 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg text-center">
            <MessageSquare className="h-5 w-5 mx-auto mb-1 text-purple-600" />
            <p className="text-xs text-slate-500 mb-1">Communication</p>
            <p className="font-bold text-slate-900 dark:text-white">
              {trustData.metrics?.communication?.toFixed(1) || 'N/A'}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Rating submission component (for buyers post-transaction)
const SubmitSellerRating = ({ sellerId, auctionId, auctionType, onSubmit }) => {
  const [ratings, setRatings] = useState({
    pickup_speed: 0,
    item_accuracy: 0,
    communication: 0
  });
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const overallRating = Math.round(
        (ratings.pickup_speed + ratings.item_accuracy + ratings.communication) / 3
      );
      
      await axios.post(`${API}/ratings`, {
        auction_id: auctionId,
        auction_type: auctionType,
        target_user_id: sellerId,
        rating: overallRating,
        comment,
        metrics: ratings
      }, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      });
      
      if (onSubmit) onSubmit();
    } catch (error) {
      console.error('Failed to submit rating:', error);
    } finally {
      setSubmitting(false);
    }
  };

  const handleStarClick = (category, value) => {
    setRatings(prev => ({ ...prev, [category]: value }));
  };

  const renderStarInput = (category, label, icon) => (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map(value => (
          <button
            key={value}
            onClick={() => handleStarClick(category, value)}
            className="focus:outline-none"
          >
            <Star 
              className={`h-6 w-6 transition-colors ${
                value <= ratings[category] 
                  ? 'fill-amber-400 text-amber-400' 
                  : 'text-slate-300 hover:text-amber-300'
              }`}
            />
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <Card data-testid="submit-seller-rating">
      <CardContent className="p-4 space-y-4">
        <h4 className="font-semibold text-lg">Rate Your Experience</h4>
        
        {renderStarInput('pickup_speed', 'Pickup Speed', <Clock className="h-4 w-4 text-blue-600" />)}
        {renderStarInput('item_accuracy', 'Item as Described', <Package className="h-4 w-4 text-green-600" />)}
        {renderStarInput('communication', 'Communication', <MessageSquare className="h-4 w-4 text-purple-600" />)}
        
        <textarea
          className="w-full p-3 border rounded-lg text-sm"
          placeholder="Optional: Share your experience..."
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
        />
        
        <button
          onClick={handleSubmit}
          disabled={submitting || (ratings.pickup_speed === 0 && ratings.item_accuracy === 0 && ratings.communication === 0)}
          className="w-full py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-lg disabled:opacity-50"
        >
          {submitting ? 'Submitting...' : 'Submit Rating'}
        </button>
      </CardContent>
    </Card>
  );
};

export { TrustBadge, StarRating, TrustScoreDisplay, SubmitSellerRating };
export default TrustScoreDisplay;
