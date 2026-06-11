import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Button } from './ui/button';
import { Bell, BellOff, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';

const API = API_BASE;

/**
 * iter300 P2 — "Follow Seller" toggle. Followers get an email + platform
 * notification whenever the seller posts a new listing.
 */
export const FollowSellerButton = ({ sellerId, size = 'sm', className = '' }) => {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const isFrench = (i18n.language || 'en').startsWith('fr');

  const [following, setFollowing] = useState(false);
  const [count, setCount] = useState(null);
  const [busy, setBusy] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/sellers/${sellerId}/follow-status`,
        token ? { headers: { Authorization: `Bearer ${token}` } } : undefined);
      setFollowing(res.data.following);
      setCount(res.data.followers_count);
    } catch { /* non-blocking */ }
  }, [sellerId, token]);

  useEffect(() => { if (sellerId) fetchStatus(); }, [sellerId, fetchStatus]);

  if (user?.id === sellerId) return null; // can't follow yourself

  const toggle = async () => {
    if (!token) {
      toast.info(isFrench ? 'Connectez-vous pour suivre ce vendeur' : 'Log in to follow this seller');
      navigate('/auth');
      return;
    }
    setBusy(true);
    try {
      const res = following
        ? await axios.delete(`${API}/sellers/${sellerId}/follow`, { headers: { Authorization: `Bearer ${token}` } })
        : await axios.post(`${API}/sellers/${sellerId}/follow`, {}, { headers: { Authorization: `Bearer ${token}` } });
      setFollowing(res.data.following);
      setCount(res.data.followers_count);
      toast.success(res.data.following
        ? (isFrench ? 'Vous suivez maintenant ce vendeur — vous serez averti de ses nouvelles annonces' : "Following — you'll be notified when this seller posts new listings")
        : (isFrench ? 'Vous ne suivez plus ce vendeur' : 'Unfollowed seller'));
    } catch (err) {
      toast.error(err.response?.data?.detail || (isFrench ? 'Échec de la mise à jour' : 'Failed to update follow'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      size={size}
      variant={following ? 'secondary' : 'default'}
      onClick={toggle}
      disabled={busy}
      className={className}
      data-testid="follow-seller-btn"
    >
      {busy ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
        : following ? <BellOff className="h-3.5 w-3.5 mr-1.5" /> : <Bell className="h-3.5 w-3.5 mr-1.5" />}
      {following
        ? (isFrench ? 'Suivi' : 'Following')
        : (isFrench ? 'Suivre le vendeur' : 'Follow Seller')}
      {count !== null && count > 0 && <span className="ml-1.5 opacity-70">({count})</span>}
    </Button>
  );
};

export default FollowSellerButton;
