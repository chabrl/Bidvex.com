import React, { useState, useEffect } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * WatchLotButton Component
 * Allows users to watch/unwatch specific lots in multi-item auctions
 * 
 * @param {string} listingId - ID of the multi-item listing
 * @param {number} lotNumber - Lot number within the listing
 * @param {string} variant - Button variant ('default', 'outline', 'ghost')
 * @param {string} size - Button size ('sm', 'default', 'lg')
 */
const WatchLotButton = ({ listingId, lotNumber, variant = 'outline', size = 'sm' }) => {
  const { user } = useAuth();
  const [isWatching, setIsWatching] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user && listingId && lotNumber !== undefined) {
      checkWatchStatus();
    }
  }, [user, listingId, lotNumber]);

  const checkWatchStatus = async () => {
    try {
      const response = await axios.get(`${API}/lots/watched/check`, {
        params: { listing_id: listingId, lot_number: lotNumber }
      });
      setIsWatching(response.data.is_watching);
    } catch (error) {
      console.error('Failed to check watch status:', error);
    }
  };

  const toggleWatch = async (e) => {
    e.stopPropagation();
    
    if (!user) {
      toast.error('Please log in to watch lots');
      return;
    }

    try {
      setLoading(true);
      
      const endpoint = isWatching ? '/lots/unwatch' : '/lots/watch';
      const response = await axios.post(`${API}${endpoint}`, {
        listing_id: listingId,
        lot_number: lotNumber
      });

      setIsWatching(!isWatching);
      toast.success(response.data.message);
    } catch (error) {
      console.error('Failed to toggle watch:', error);
      const errorMsg = error.response?.data?.detail || 'Failed to update watch status';
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return null;
  }

  return (
    <Button
      variant={variant}
      size={size}
      onClick={toggleWatch}
      disabled={loading}
      className={isWatching ? 'border-blue-500 text-blue-600' : ''}
      title={isWatching ? 'Stop watching this lot' : 'Watch this lot'}
    >
      {isWatching ? (
        <>
          <EyeOff className="h-4 w-4 mr-1" />
          Watching
        </>
      ) : (
        <>
          <Eye className="h-4 w-4 mr-1" />
          Watch
        </>
      )}
    </Button>
  );
};

export default WatchLotButton;
