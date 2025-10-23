import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { TrendingUp, Trash2, Plus, Star } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PromotionManager = () => {
  const [promotions, setPromotions] = useState([]);
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newPromotion, setNewPromotion] = useState({
    listing_id: '',
    promotion_type: 'featured',
    end_date: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [promotionsRes, listingsRes] = await Promise.all([
        axios.get(`${API}/admin/promotions`),
        axios.get(`${API}/admin/auctions?status=active`)
      ]);
      setPromotions(promotionsRes.data);
      setListings(listingsRes.data);
    } catch (error) {
      toast.error('Failed to load promotions');
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePromotion = async () => {
    try {
      await axios.post(`${API}/admin/promotions/create`, newPromotion);
      toast.success('Promotion created successfully');
      setShowCreate(false);
      setNewPromotion({ listing_id: '', promotion_type: 'featured', end_date: '' });
      fetchData();
    } catch (error) {
      toast.error('Failed to create promotion');
    }
  };

  const handleDeletePromotion = async (promotionId) => {
    if (window.confirm('Delete this promotion?')) {
      try {
        await axios.delete(`${API}/admin/promotions/${promotionId}`);
        toast.success('Promotion deleted');
        fetchData();
      } catch (error) {
        toast.error('Failed to delete promotion');
      }
    }
  };

  const handleFeatureListing = async (listingId, isFeatured) => {
    try {
      await axios.put(`${API}/admin/listings/${listingId}/feature`, { is_featured: !isFeatured });
      toast.success(`Listing ${!isFeatured ? 'featured' : 'unfeatured'}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update listing');
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><TrendingUp className="h-6 w-6" />Promotion Management</h2>
          <p className="text-muted-foreground">Create and manage listing promotions</p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} className="gradient-button text-white border-0">
          <Plus className="h-4 w-4 mr-2" />Create Promotion
        </Button>
      </div>

      {showCreate && (
        <Card className="border-2 border-primary">
          <CardHeader><CardTitle>Create New Promotion</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Select Listing</label>
              <select value={newPromotion.listing_id} onChange={(e) => setNewPromotion({...newPromotion, listing_id: e.target.value})} className="w-full px-3 py-2 border rounded-md">
                <option value="">Choose a listing...</option>
                {listings.map(listing => (
                  <option key={listing.id} value={listing.id}>{listing.title}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Promotion Type</label>
              <select value={newPromotion.promotion_type} onChange={(e) => setNewPromotion({...newPromotion, promotion_type: e.target.value})} className="w-full px-3 py-2 border rounded-md">
                <option value="featured">Featured</option>
                <option value="premium">Premium</option>
                <option value="basic">Basic</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">End Date</label>
              <Input type="datetime-local" value={newPromotion.end_date} onChange={(e) => setNewPromotion({...newPromotion, end_date: e.target.value})} />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreatePromotion} className="gradient-button text-white border-0">Create</Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Active Promotions ({promotions.length})</CardTitle></CardHeader>
        <CardContent>
          {promotions.length > 0 ? (
            <div className="space-y-2">
              {promotions.map(promo => (
                <div key={promo.id} className="flex justify-between items-center p-4 border rounded-lg">
                  <div>
                    <p className="font-semibold">Listing ID: {promo.listing_id}</p>
                    <p className="text-sm text-muted-foreground">Type: {promo.promotion_type}</p>
                    <p className="text-xs text-muted-foreground">Ends: {new Date(promo.end_date).toLocaleDateString()}</p>
                  </div>
                  <div className="flex gap-2">
                    <Badge className="gradient-bg text-white border-0">{promo.status}</Badge>
                    <Button size="sm" variant="destructive" onClick={() => handleDeletePromotion(promo.id)}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No active promotions</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Feature Listings Manually</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {listings.slice(0, 10).map(listing => (
              <div key={listing.id} className="flex justify-between items-center p-4 border rounded-lg">
                <div className="flex-1">
                  <p className="font-semibold">{listing.title}</p>
                  <p className="text-sm text-muted-foreground">${listing.current_price}</p>
                </div>
                <Button size="sm" variant={listing.is_featured ? "default" : "outline"} onClick={() => handleFeatureListing(listing.id, listing.is_featured)}>
                  <Star className="h-4 w-4 mr-2" />{listing.is_featured ? 'Featured' : 'Feature'}
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PromotionManager;