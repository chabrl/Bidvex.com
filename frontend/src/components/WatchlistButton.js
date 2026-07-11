import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { Heart } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import axios from 'axios';

const API = API_BASE;

const WatchlistButton = ({ 
  itemId,  // Can be listingId, auctionId, or lotId
  itemType = 'listing',  // 'listing', 'auction', or 'lot'
  className = '', 
  size = 'default', 
  showLabel = false,
  // Legacy support
  listingId,
  auctionId,
  lotId
}) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [isInWatchlist, setIsInWatchlist] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  // Determine the actual item ID and type (support legacy props)
  const actualItemId = itemId || listingId || auctionId || lotId;
  const actualItemType = itemId ? itemType : (listingId ? 'listing' : (auctionId ? 'auction' : 'lot'));

  // Size variants
  const sizeClasses = {
    small: 'h-5 w-5',
    default: 'h-6 w-6',
    large: 'h-8 w-8'
  };

  useEffect(() => {
    if (user && actualItemId) {
      checkWatchlistStatus();
    }
  }, [user, actualItemId, actualItemType]);

  const checkWatchlistStatus = async () => {
    try {
      const response = await axios.get(`${API}/watchlist`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      });

      // iter345 BUG-2 — fully-typed presence check (previously only
      // listing/auction/lot were verified → heart never lit up for
      // vehicle / storage / vehicle_multi_lot).
      const bucketByType = {
        listing:            response.data.listings || [],
        auction:            response.data.auctions || [],
        vehicle:            response.data.vehicles || [],
        storage:            response.data.storage || [],
        vehicle_multi_lot:  response.data.vehicle_multi_lot || [],
      };
      let isWatched = false;
      if (actualItemType === 'lot') {
        isWatched = (response.data.lots || []).some(
          (item) => item.lot?.lot_number && item.auction_id &&
                    `${item.auction_id}:${item.lot.lot_number}` === actualItemId
        );
      } else {
        const bucket = bucketByType[actualItemType] || [];
        isWatched = bucket.some((item) => item.id === actualItemId);
      }

      setIsInWatchlist(isWatched);
    } catch (error) {
      console.error('Error checking watchlist status:', error);
    }
  };

  const handleToggleWatchlist = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    // Require authentication
    if (!user) {
      toast.error('Please sign in to add items to your watchlist');
      navigate('/auth');
      return;
    }

    setIsLoading(true);
    setIsAnimating(true);

    try {
      if (isInWatchlist) {
        // Remove from watchlist
        await axios.post(`${API}/watchlist/remove`, null, {
          params: { item_id: actualItemId, item_type: actualItemType },
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
        });
        setIsInWatchlist(false);
        toast.success('Removed from watchlist', {
          icon: '💔',
          duration: 2000
        });
      } else {
        // Add to watchlist
        await axios.post(`${API}/watchlist/add`, null, {
          params: { item_id: actualItemId, item_type: actualItemType },
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
        });
        setIsInWatchlist(true);
        toast.success('Added to watchlist', {
          icon: '❤️',
          duration: 2000
        });
      }
    } catch (error) {
      console.error('Error toggling watchlist:', error);
      toast.error('Failed to update watchlist. Please try again.');
    } finally {
      setIsLoading(false);
      // Keep animation for a bit longer
      setTimeout(() => setIsAnimating(false), 300);
    }
  };

  return (
    <button
      onClick={handleToggleWatchlist}
      disabled={isLoading}
      data-testid={`watchlist-btn-${actualItemType}-${actualItemId}`}
      className={`
        inline-flex items-center gap-2 transition-all duration-200
        hover:scale-110 active:scale-95
        ${isAnimating ? 'animate-pulse' : ''}
        ${className}
      `}
      aria-label={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
      title={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
    >
      <Heart
        className={`
          ${sizeClasses[size]}
          transition-all duration-200
          ${isInWatchlist 
            ? 'fill-red-500 stroke-red-500' 
            : 'fill-none stroke-current hover:stroke-red-500'
          }
          ${isLoading ? 'opacity-50' : ''}
        `}
      />
      {showLabel && (
        <span className="text-sm font-medium">
          {isInWatchlist ? 'Saved' : 'Save'}
        </span>
      )}
    </button>
  );
};

export default WatchlistButton;
