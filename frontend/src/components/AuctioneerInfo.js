import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, MapPin, Award, TrendingUp, Star } from 'lucide-react';
import { Badge } from './ui/badge';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * AuctioneerInfo Component
 * Displays auctioneer/seller information with profile summary and ratings
 * 
 * @param {string} sellerId - User ID of the auctioneer
 * @param {string} variant - Display variant: 'compact', 'full', 'tooltip'
 * @param {string} className - Additional CSS classes
 */
const AuctioneerInfo = ({ sellerId, variant = 'compact', className = '' }) => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [ratings, setRatings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!sellerId) {
        setLoading(false);
        return;
      }

      try {
        const [profileRes, ratingsRes] = await Promise.all([
          axios.get(`${API}/users/${sellerId}/profile-summary`),
          axios.get(`${API}/users/${sellerId}/ratings`)
        ]);
        
        setProfile(profileRes.data);
        setRatings(ratingsRes.data);
      } catch (err) {
        console.error('Failed to fetch auctioneer data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [sellerId]);

  if (loading) {
    return (
      <div className={`flex items-center gap-2 text-sm text-muted-foreground ${className}`}>
        <User className="h-4 w-4 animate-pulse" />
        <span className="animate-pulse">Loading...</span>
      </div>
    );
  }

  if (error || !profile) {
    return null;
  }

  // Compact variant - for auction cards
  if (variant === 'compact') {
    return (
      <div className={`flex items-center gap-2 text-sm ${className}`}>
        <User className="h-4 w-4 text-muted-foreground" />
        <div className="flex items-center gap-2 flex-wrap">
          <span 
            className="font-medium text-foreground hover:text-primary cursor-pointer hover:underline"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/seller/${sellerId}`);
            }}
          >
            {profile.company_name || profile.name}
          </span>
          {profile.subscription_tier !== 'free' && (
            <Badge 
              variant="secondary" 
              className={`text-xs ${
                profile.subscription_tier === 'vip' 
                  ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0' 
                  : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white border-0'
              }`}
            >
              {profile.subscription_tier === 'vip' ? 'VIP' : 'Premium'}
            </Badge>
          )}
          {ratings && ratings.total_ratings > 0 && (
            <div className="flex items-center gap-1">
              <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
              <span className="font-medium">{ratings.average_rating}</span>
              <span className="text-muted-foreground">({ratings.total_ratings})</span>
            </div>
          )}
        </div>
        {profile.city && (
          <span className="text-muted-foreground flex items-center gap-1">
            <MapPin className="h-3 w-3" />
            {profile.city}
          </span>
        )}
      </div>
    );
  }

  // Full variant - for detail pages
  if (variant === 'full') {
    return (
      <div className={`p-4 bg-muted/30 rounded-lg border ${className}`}>
        <div className="flex items-start gap-4">
          {/* Profile Image */}
          <div className="flex-shrink-0">
            {profile.picture ? (
              <img
                src={profile.picture}
                alt={profile.name}
                className="h-16 w-16 rounded-full object-cover border-2 border-primary/20"
              />
            ) : (
              <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
                <User className="h-8 w-8 text-primary" />
              </div>
            )}
          </div>

          {/* Profile Details */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-semibold">
                {profile.company_name || profile.name}
              </h3>
              {profile.subscription_tier !== 'free' && (
                <Badge 
                  className={
                    profile.subscription_tier === 'vip' 
                      ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0' 
                      : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white border-0'
                  }
                >
                  {profile.subscription_tier === 'vip' ? 'VIP Seller' : 'Premium Seller'}
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-4 text-sm text-muted-foreground mb-3">
              {profile.city && (
                <div className="flex items-center gap-1">
                  <MapPin className="h-4 w-4" />
                  <span>{profile.city}</span>
                </div>
              )}
              {ratings && ratings.total_ratings > 0 && (
                <div className="flex items-center gap-1">
                  <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                  <span className="font-semibold text-foreground">{ratings.average_rating}</span>
                  <span>({ratings.total_ratings} {ratings.total_ratings === 1 ? 'rating' : 'ratings'})</span>
                </div>
              )}
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-primary" />
                <div>
                  <p className="text-muted-foreground">Total Auctions</p>
                  <p className="font-semibold">{profile.stats?.total_auctions || 0}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-green-600" />
                <div>
                  <p className="text-muted-foreground">Completed</p>
                  <p className="font-semibold">{profile.stats?.completed_auctions || 0}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Tooltip variant - for hover cards
  if (variant === 'tooltip') {
    return (
      <div className={`p-3 bg-background border rounded-lg shadow-lg w-64 ${className}`}>
        <div className="flex items-start gap-3">
          {profile.picture ? (
            <img
              src={profile.picture}
              alt={profile.name}
              className="h-12 w-12 rounded-full object-cover"
            />
          ) : (
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
              <User className="h-6 w-6 text-primary" />
            </div>
          )}
          
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm truncate">
              {profile.company_name || profile.name}
            </p>
            {profile.city && (
              <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                <MapPin className="h-3 w-3" />
                {profile.city}
              </p>
            )}
            <div className="mt-2 text-xs text-muted-foreground">
              <p>{profile.stats?.total_auctions || 0} auctions hosted</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default AuctioneerInfo;
