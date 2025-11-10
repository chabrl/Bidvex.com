import React, { useState, useEffect } from 'react';
import { Heart } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WishlistHeartButton = ({ auctionId, lotId = null, initialWishlisted = false, size = "default", showCount = false, wishlistCount = 0 }) => {
  const { user } = useAuth();
  const [isWishlisted, setIsWishlisted] = useState(initialWishlisted);
  const [count, setCount] = useState(wishlistCount);
  const [loading, setLoading] = useState(false);

  const toggleWishlist = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (!user) {
      toast.error('Please login to add items to wishlist');
      return;
    }

    setLoading(true);
    try {
      if (isWishlisted) {
        // Remove from wishlist
        await axios.delete(`${API}/wishlist/${auctionId}`);
        setIsWishlisted(false);
        setCount(prev => Math.max(0, prev - 1));
        toast.success('Removed from wishlist');
      } else {
        // Add to wishlist
        await axios.post(`${API}/wishlist`, null, {
          params: { auction_id: auctionId, lot_id: lotId }
        });
        setIsWishlisted(true);
        setCount(prev => prev + 1);
        toast.success('Added to wishlist');
      }
    } catch (error) {
      console.error('Wishlist error:', error);
      toast.error(error.response?.data?.detail || 'Failed to update wishlist');
    } finally {
      setLoading(false);
    }
  };

  const sizeClasses = {
    small: 'h-4 w-4',
    default: 'h-5 w-5',
    large: 'h-6 w-6'
  };

  return (
    <button
      onClick={toggleWishlist}
      disabled={loading}
      className={`flex items-center gap-1 p-2 rounded-full transition-all ${
        isWishlisted 
          ? 'bg-red-50 text-red-500 hover:bg-red-100' 
          : 'bg-white/80 text-gray-600 hover:bg-white hover:text-red-500'
      } ${loading ? 'opacity-50 cursor-not-allowed' : 'hover:scale-110'}`}
      aria-label={isWishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
    >
      <Heart 
        className={`${sizeClasses[size]} ${isWishlisted ? 'fill-current' : ''}`}
      />
      {showCount && count > 0 && (
        <span className="text-xs font-medium">{count}</span>
      )}
    </button>
  );
};

export default WishlistHeartButton;
