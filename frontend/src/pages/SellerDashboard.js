import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Plus, DollarSign, Package, FileText, ShoppingBag, Heart, Eye, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SellerDashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/seller`);
      setDashboard(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
      toast.error(t('dashboard.seller.loadFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteListing = async (listingId) => {
    if (window.confirm(t('dashboard.seller.deleteListing'))) {
      try {
        await axios.delete(`${API}/listings/${listingId}`);
        toast.success(t('dashboard.seller.listingDeleted'));
        fetchDashboard();
      } catch (error) {
        toast.error(t('dashboard.seller.deleteFailed'));
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4" data-testid="seller-dashboard">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold mb-2">{t('dashboard.seller.title')}</h1>
            <p className="text-sm text-muted-foreground">
              {user.account_type === 'business' ? t('dashboard.seller.businessAccount') : t('dashboard.seller.personalAccount')} - 
              {t('dashboard.seller.commissionRate')}: {user.account_type === 'business' ? '4.5%' : '5%'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              className="gradient-button text-white border-0"
              onClick={() => navigate('/create-listing')}
              data-testid="create-listing-btn"
            >
              <Plus className="mr-2 h-4 w-4" />
              {t('dashboard.seller.createListing')}
            </Button>
            {user.account_type === 'business' && (
              <Button
                variant="outline"
                onClick={() => navigate('/create-multi-item-listing')}
                data-testid="create-lot-btn"
              >
                <Package className="mr-2 h-4 w-4" />
                {t('dashboard.seller.createLot', 'Create Lot')}
              </Button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            icon={<Package className="h-6 w-6" />}
            title={t('dashboard.seller.activeListings')}
            value={dashboard?.active_listings || 0}
            color="blue"
          />
          <StatCard
            icon={<ShoppingBag className="h-6 w-6" />}
            title={t('dashboard.seller.soldItems')}
            value={dashboard?.sold_listings || 0}
            color="green"
          />
          <StatCard
            icon={<FileText className="h-6 w-6" />}
            title={t('dashboard.seller.draftListings')}
            value={dashboard?.draft_listings || 0}
            color="orange"
          />
          <StatCard
            icon={<DollarSign className="h-6 w-6" />}
            title={t('dashboard.seller.totalSales')}
            value={`$${dashboard?.total_sales?.toFixed(2) || '0.00'}`}
            color="purple"
          />
        </div>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>Your Listings</CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard?.listings && dashboard.listings.length > 0 ? (
              <div className="space-y-4">
                {dashboard.listings.map((listing) => (
                  <div
                    key={listing.id}
                    className="flex flex-col sm:flex-row gap-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                    data-testid={`listing-item-${listing.id}`}
                  >
                    <div className="w-full sm:w-24 h-24 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
                      {listing.images && listing.images[0] ? (
                        <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">📦</div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <h3 className="font-semibold truncate">{listing.title}</h3>
                        <Badge variant={listing.status === 'active' ? 'default' : 'secondary'}>
                          {listing.status}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm mb-2">
                        <span className="text-green-600 font-semibold">
                          <DollarSign className="h-3 w-3 inline mr-1" />
                          ${listing.current_price.toFixed(2)}
                        </span>
                        <span className="text-blue-600">
                          <TrendingUp className="h-3 w-3 inline mr-1" />
                          {listing.bid_count} bids
                        </span>
                        <span className="text-gray-600">
                          <Eye className="h-3 w-3 inline mr-1" />
                          {listing.views} views
                        </span>
                        <span className="text-red-600">
                          <Heart className="h-3 w-3 inline mr-1 fill-current" />
                          {listing.wishlist_count || 0} wishlisted
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/listing/${listing.id}`)}
                        >
                          View
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteListing(listing.id)}
                          data-testid={`delete-listing-${listing.id}`}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <Package className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No listings yet</p>
                <Button onClick={() => navigate('/create-listing')} className="gradient-button text-white border-0">
                  Create Your First Listing
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const StatCard = ({ icon, title, value, color }) => (
  <Card className="glassmorphism">
    <CardContent className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-xl bg-${color}-100 dark:bg-${color}-900/20 text-${color}-600`}>
          {icon}
        </div>
      </div>
      <p className="text-2xl font-bold mb-1">{value}</p>
      <p className="text-sm text-muted-foreground">{title}</p>
    </CardContent>
  </Card>
);

export default SellerDashboard;
