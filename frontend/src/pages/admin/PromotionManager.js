import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { AsyncButton } from '../../components/ui/async-button';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { toast } from 'sonner';
import { TrendingUp, Trash2, Plus, Star, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

const PromotionManager = () => {
  const { token } = useAuth();
  const headers = React.useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);
  const { t } = useTranslation();
  const [promotions, setPromotions] = useState([]);
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newPromotion, setNewPromotion] = useState({
    listing_id: '',
    promotion_type: 'featured',
    end_date: ''
  });
  const [search, setSearch] = useState('');
  const [confirm, setConfirm] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [promotionsRes, listingsRes] = await Promise.all([
        axios.get(`${API}/admin/promotions`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/admin/auctions?status=active`, { headers }).catch(() => ({ data: [] }))
      ]);
      setPromotions(Array.isArray(promotionsRes.data) ? promotionsRes.data : []);
      setListings(Array.isArray(listingsRes.data) ? listingsRes.data : []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to load promotions');
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const createPromotion = async () => {
    if (!newPromotion.listing_id) {
      toast.error('Please select a listing / Veuillez sélectionner une annonce');
      throw new Error('validation');
    }
    if (!newPromotion.end_date) {
      toast.error('End date is required / Date de fin requise');
      throw new Error('validation');
    }
    if (new Date(newPromotion.end_date) <= new Date()) {
      toast.error('End date must be in the future / La date de fin doit être future');
      throw new Error('validation');
    }
    await axios.post(`${API}/admin/promotions/create`, newPromotion, { headers });
    setShowCreate(false);
    setNewPromotion({ listing_id: '', promotion_type: 'featured', end_date: '' });
    await fetchData();
  };

  const deletePromotion = async (promotionId) => {
    await axios.delete(`${API}/admin/promotions/${promotionId}`, { headers });
    await fetchData();
  };

  const featureListing = async (listingId, isFeatured) => {
    await axios.put(`${API}/admin/listings/${listingId}/feature`,
      { is_featured: !isFeatured }, { headers });
    await fetchData();
  };

  const filteredListings = listings.filter(l =>
    !search || (l.title || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6" data-testid="promotion-manager">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <TrendingUp className="h-6 w-6" />Promotion Management
          </h2>
          <p className="text-muted-foreground">Feature listings and manage active promotions</p>
        </div>
        <Button onClick={() => setShowCreate(s => !s)} className="gradient-button text-white border-0"
          data-testid="promotion-create-toggle">
          <Plus className="h-4 w-4 mr-2" />Create Promotion
        </Button>
      </div>

      {showCreate && (
        <Card className="border-2 border-primary" data-testid="promotion-create-form">
          <CardHeader><CardTitle>{t("admin.createNewPromotion")}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Select Listing</label>
              <select value={newPromotion.listing_id}
                onChange={(e) => setNewPromotion({ ...newPromotion, listing_id: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                data-testid="promotion-listing-select">
                <option value="">Choose a listing...</option>
                {listings.map(listing => (
                  <option key={listing.id} value={listing.id}>{listing.title}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Promotion Type</label>
              <select value={newPromotion.promotion_type}
                onChange={(e) => setNewPromotion({ ...newPromotion, promotion_type: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                data-testid="promotion-type-select">
                <option value="featured">{t("homepage.featured")}</option>
                <option value="premium">Premium</option>
                <option value="basic">Basic</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">End Date</label>
              <Input type="datetime-local" value={newPromotion.end_date}
                onChange={(e) => setNewPromotion({ ...newPromotion, end_date: e.target.value })}
                data-testid="promotion-end-date" />
            </div>
            <div className="flex gap-2">
              <AsyncButton onAction={createPromotion} className="gradient-button text-white border-0"
                successMessage="Promotion created" loadingText="Creating…"
                data-testid="promotion-submit-btn">
                Create
              </AsyncButton>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Active Promotions ({promotions.length})</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : promotions.length > 0 ? (
            <div className="space-y-2">
              {promotions.map(promo => (
                <div key={promo.id} className="flex justify-between items-center p-4 border rounded-lg"
                  data-testid={`promotion-row-${promo.id}`}>
                  <div>
                    <p className="font-semibold">Listing ID: {promo.listing_id}</p>
                    <p className="text-sm text-muted-foreground">Type: {promo.promotion_type}</p>
                    <p className="text-xs text-muted-foreground">
                      Ends: {promo.end_date ? new Date(promo.end_date).toLocaleDateString() : '—'}
                    </p>
                    {typeof promo.usage_count === 'number' && (
                      <p className="text-xs text-muted-foreground">
                        Usage: {promo.usage_count}{promo.max_uses ? ` / ${promo.max_uses}` : ''}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Badge className="gradient-bg text-white border-0">{promo.status || 'active'}</Badge>
                    <Button size="sm" variant="destructive"
                      data-testid={`promotion-delete-${promo.id}`}
                      onClick={() => setConfirm({
                        title: 'Delete this promotion?',
                        description: `Promotion for listing ${promo.listing_id} will be permanently removed.`,
                        variant: 'destructive',
                        confirmText: 'Delete',
                        onConfirm: () => deletePromotion(promo.id),
                        successMessage: 'Promotion deleted',
                      })}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
              No active promotions<br />
              <span className="text-xs">Aucune promotion active</span>
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle>{t("admin.featureListingsManually")}</CardTitle>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input className="pl-9" placeholder="Search listings…"
                value={search} onChange={(e) => setSearch(e.target.value)}
                data-testid="feature-listings-search" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : filteredListings.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No listings match your search.</p>
          ) : (
            <div className="space-y-2">
              {filteredListings.slice(0, 20).map(listing => (
                <div key={listing.id} className="flex justify-between items-center p-4 border rounded-lg">
                  <div className="flex-1">
                    <p className="font-semibold">{listing.title}</p>
                    <p className="text-sm text-muted-foreground">${listing.current_price}</p>
                  </div>
                  <AsyncButton size="sm"
                    variant={listing.is_featured ? 'default' : 'outline'}
                    onAction={() => featureListing(listing.id, listing.is_featured)}
                    successMessage={listing.is_featured ? 'Unfeatured' : 'Featured'}
                    data-testid={`feature-listing-btn-${listing.id}`}>
                    <Star className="h-4 w-4 mr-2" />
                    {listing.is_featured ? 'Featured' : 'Feature'}
                  </AsyncButton>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />
    </div>
  );
};

export default PromotionManager;
