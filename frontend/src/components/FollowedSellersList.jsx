import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';

import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { TopSellerBadge } from './TopSellerBadge';
import { Store, BellOff, Loader2, Users } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { LangLink } from './LangLink';

const API = API_BASE;

/**
 * iter300 P2 — "Sellers I Follow" panel (Buyer Dashboard tab).
 */
export const FollowedSellersList = () => {
  const { token } = useAuth();
  const { i18n } = useTranslation();
  const isFrench = (i18n.language || 'en').startsWith('fr');
  const [rows, setRows] = useState(null);

  const fetchRows = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/me/followed-sellers`,
        { headers: { Authorization: `Bearer ${token}` } });
      setRows(res.data.sellers || []);
    } catch { setRows([]); }
  }, [token]);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  const unfollow = async (sellerId) => {
    try {
      await axios.delete(`${API}/sellers/${sellerId}/follow`,
        { headers: { Authorization: `Bearer ${token}` } });
      setRows((prev) => prev.filter((r) => r.seller_id !== sellerId));
      toast.success(isFrench ? 'Vous ne suivez plus ce vendeur' : 'Unfollowed seller');
    } catch {
      toast.error(isFrench ? 'Échec' : 'Failed to unfollow');
    }
  };

  if (rows === null) {
    return <div className="flex justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }
  if (rows.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground" data-testid="followed-sellers-empty">
        <Users className="h-10 w-10 mx-auto mb-3 opacity-40" />
        <p className="text-sm">
          {isFrench
            ? 'Vous ne suivez aucun vendeur. Visitez une vitrine et cliquez « Suivre le vendeur » pour être averti de ses nouvelles annonces.'
            : 'You are not following any sellers yet. Visit a storefront and click "Follow Seller" to get notified of new listings.'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="followed-sellers-list">
      {rows.map((s) => (
        <Card key={s.seller_id} data-testid={`followed-seller-${s.seller_id}`}>
          <CardContent className="py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-full bg-slate-200 overflow-hidden flex items-center justify-center shrink-0">
                {s.picture
                  ? <img src={s.picture} alt={s.name} className="w-full h-full object-cover" />
                  : <span className="font-bold text-slate-500">{s.name?.charAt(0) || 'S'}</span>}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <LangLink to={`/store/${s.seller_id}`} className="font-semibold hover:underline truncate">
                    {s.name}
                  </LangLink>
                  {s.is_top_seller && <TopSellerBadge size="xs" />}
                </div>
                <p className="text-xs text-muted-foreground">
                  {isFrench
                    ? `${s.active_listings} annonce(s) active(s)`
                    : `${s.active_listings} active listing(s)`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button asChild size="sm" variant="outline">
                <LangLink to={`/store/${s.seller_id}`} data-testid={`view-store-${s.seller_id}`}>
                  <Store className="h-3.5 w-3.5 mr-1.5" />
                  {isFrench ? 'Vitrine' : 'Store'}
                </LangLink>
              </Button>
              <Button size="sm" variant="ghost" className="text-red-600 hover:bg-red-50"
                onClick={() => unfollow(s.seller_id)} data-testid={`unfollow-${s.seller_id}`}>
                <BellOff className="h-3.5 w-3.5 mr-1.5" />
                {isFrench ? 'Ne plus suivre' : 'Unfollow'}
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export default FollowedSellersList;
