import React, { useState, useEffect } from 'react';
import { Heart } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WatchlistButton = ({ listingId, className = '', size = 'default', showLabel = false }) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [isInWatchlist, setIsInWatchlist] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  // Size variants
  const sizeClasses = {
    small: 'h-5 w-5',
    default: 'h-6 w-6',
    large: 'h-8 w-8'
  };

  useEffect(() => {
    if (user && listingId) {
      checkWatchlistStatus();
    }
  }, [user, listingId]);

  const checkWatchlistStatus = async () => {
    try {
      const response = await axios.get(`${API}/watchlist/check/${listingId}`);
      setIsInWatchlist(response.data.in_watchlist);
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
          params: { listing_id: listingId }
        });
        setIsInWatchlist(false);
        toast.success('Removed from watchlist', {
          icon: '💔',
          duration: 2000
        });
      } else {
        // Add to watchlist
        await axios.post(`${API}/watchlist/add`, null, {
          params: { listing_id: listingId }
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
