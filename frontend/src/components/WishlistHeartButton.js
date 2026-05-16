import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { Heart } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';

const API = API_BASE;

const WishlistHeartButton = ({
  auctionId,
  lotId = null,
  initialWishlisted = false,
  size = 'default',
  showCount = false,
  wishlistCount = 0,
}) => {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [isWishlisted, setIsWishlisted] = useState(initialWishlisted);
  const [count, setCount] = useState(wishlistCount);
  const [loading, setLoading] = useState(false);

  // iter217 Bug 6 — fetch real wishlist state on mount so the heart
  // icon renders the correct filled/unfilled state on every detail page.
  useEffect(() => {
    if (!user || !auctionId) return;
    let cancelled = false;
    (async () => {
      try {
        const params = lotId ? { params: { lot_id: lotId } } : undefined;
        const { data } = await axios.get(`${API}/wishlist/status/${auctionId}`, params);
        if (!cancelled && data && typeof data.is_wishlisted === 'boolean') {
          setIsWishlisted(data.is_wishlisted);
        }
      } catch (err) {
        // Silent — fall back to initialWishlisted prop.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, auctionId, lotId]);

  const toggleWishlist = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (!user) {
      toast.error(t('wishlist.loginRequired', 'Please login to add items to wishlist'));
      return;
    }

    setLoading(true);
    try {
      if (isWishlisted) {
        await axios.delete(`${API}/wishlist/${auctionId}`);
        setIsWishlisted(false);
        setCount(prev => Math.max(0, prev - 1));
        toast.success(t('wishlist.removed', 'Removed from wishlist'));
      } else {
        await axios.post(`${API}/wishlist`, null, {
          params: { auction_id: auctionId, lot_id: lotId },
        });
        setIsWishlisted(true);
        setCount(prev => prev + 1);
        toast.success(t('wishlist.added', 'Added to wishlist'));
      }
    } catch (error) {
      // iter217 — Already-in-wishlist is not a failure; flip the state to true and exit
      const detail = error?.response?.data?.detail || '';
      if (error?.response?.status === 400 && /already/i.test(detail)) {
        setIsWishlisted(true);
        return;
      }
      console.error('Wishlist error:', error);
      toast.error(detail || t('wishlist.failed', 'Failed to update wishlist'));
    } finally {
      setLoading(false);
    }
  };

  const sizeClasses = {
    small: 'h-4 w-4',
    default: 'h-5 w-5',
    large: 'h-6 w-6',
  };

  return (
    <button
      type="button"
      onClick={toggleWishlist}
      disabled={loading}
      data-testid="wishlist-heart-btn"
      className={`flex items-center gap-1 p-2 rounded-full transition-all ${
        isWishlisted
          ? 'bg-red-50 text-red-500 hover:bg-red-100'
          : 'bg-white/80 text-gray-600 hover:bg-white hover:text-red-500'
      } ${loading ? 'opacity-50 cursor-not-allowed' : 'hover:scale-110'}`}
      aria-label={isWishlisted ? t('wishlist.removeAria', 'Remove from wishlist') : t('wishlist.addAria', 'Add to wishlist')}
    >
      <Heart className={`${sizeClasses[size]} ${isWishlisted ? 'fill-current' : ''}`} />
      {showCount && count > 0 && <span className="text-xs font-medium">{count}</span>}
    </button>
  );
};

export default WishlistHeartButton;
