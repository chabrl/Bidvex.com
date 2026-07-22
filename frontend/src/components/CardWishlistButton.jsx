/**
 * iter370 — Card wishlist button (FIX 1: pixel-perfect centering).
 *
 * The user's iter370 spec requires:
 *   • 36 × 36 white circle with `padding: 0` — any padding shifts the icon
 *     off-center.
 *   • Inline SVG (NOT lucide-react, NOT emoji) — icon-font / emoji rendering
 *     drifts per platform and OS.
 *   • `display: flex`, `align-items: center`, `justify-content: center` on
 *     the button; `display: block` + `flex-shrink: 0` on the SVG.
 *
 * This is the ONLY approved wishlist button implementation on lot cards.
 * Wraps the existing `/api/watchlist/*` endpoints so the state stays in
 * sync with the header watchlist count.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';

const CardWishlistButton = ({ itemId, itemType = 'lot' }) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [isWishlisted, setIsWishlisted] = useState(false);
  const [busy, setBusy] = useState(false);

  const authHeaders = useCallback(() => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  }), []);

  // On mount / user change, check whether this item is already in the
  // watchlist. Uses the same detailed bucket-per-type logic the header uses.
  useEffect(() => {
    let cancelled = false;
    if (!user || !itemId) { setIsWishlisted(false); return () => {}; }
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/watchlist`, { headers: authHeaders() });
        if (cancelled) return;
        let inList = false;
        if (itemType === 'lot') {
          inList = (r.data.lots || []).some(
            (row) => row.lot?.lot_number && row.auction_id &&
                     `${row.auction_id}:${row.lot.lot_number}` === itemId,
          );
        } else {
          const bucketByType = {
            listing: r.data.listings || [],
            auction: r.data.auctions || [],
            vehicle: r.data.vehicles || [],
            storage: r.data.storage || [],
            vehicle_multi_lot: r.data.vehicle_multi_lot || [],
          };
          const bucket = bucketByType[itemType] || [];
          inList = bucket.some((row) => row.id === itemId);
        }
        setIsWishlisted(inList);
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [user, itemId, itemType, authHeaders]);

  const handleWishlist = useCallback(async (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (!user) {
      toast.error('Please sign in to add items to your watchlist');
      navigate('/auth');
      return;
    }
    if (busy) return;
    setBusy(true);
    try {
      const endpoint = isWishlisted ? '/watchlist/remove' : '/watchlist/add';
      await axios.post(`${API_BASE}${endpoint}`, null, {
        params: { item_id: itemId, item_type: itemType },
        headers: authHeaders(),
      });
      setIsWishlisted((prev) => !prev);
      toast.success(isWishlisted ? 'Removed from watchlist' : 'Added to watchlist', { duration: 1600 });
    } catch (err) {
      console.error('watchlist toggle failed', err);
      toast.error('Failed to update watchlist. Please try again.');
    } finally {
      setBusy(false);
    }
  }, [user, isWishlisted, itemId, itemType, busy, authHeaders, navigate]);

  return (
    <button
      type="button"
      onClick={handleWishlist}
      style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        width: '36px',
        height: '36px',
        borderRadius: '50%',
        background: 'white',
        border: 'none',
        padding: '0',
        margin: '0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        cursor: 'pointer',
        zIndex: 10,
        lineHeight: '1',
      }}
      aria-label={isWishlisted ? 'Remove from watchlist' : 'Add to watchlist'}
      data-testid={`wishlist-btn-${itemType}-${itemId}`}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill={isWishlisted ? '#ef4444' : 'none'}
        stroke={isWishlisted ? '#ef4444' : '#6b7280'}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ display: 'block', flexShrink: 0 }}
      >
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
      </svg>
    </button>
  );
};

export default CardWishlistButton;
