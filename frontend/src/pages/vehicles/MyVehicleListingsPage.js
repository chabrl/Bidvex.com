import API_BASE from '../../config';
/**
 * My Vehicle Listings Page
 * Dashboard for sellers to manage their vehicle listings
 */

import React, { useState, useEffect, useCallback } from 'react';
import SafeImage from '../../components/SafeImage';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import {
  Car, Plus, Clock, CheckCircle, XCircle, AlertTriangle, Eye,
  DollarSign, TrendingUp, Edit, Trash2, MoreVertical
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';

const API = API_BASE;

const formatPrice = (price) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
  }).format(price);
};

const getStatusBadge = (status) => {
  const configs = {
    draft: { label: 'Draft', color: 'bg-slate-500', icon: Edit },
    pending_approval: { label: 'Pending Approval', color: 'bg-yellow-500', icon: Clock },
    approved: { label: 'Approved', color: 'bg-blue-500', icon: CheckCircle },
    active: { label: 'Active', color: 'bg-green-500', icon: TrendingUp },
    ended: { label: 'Ended', color: 'bg-slate-500', icon: Clock },
    sold: { label: 'Sold', color: 'bg-purple-500', icon: DollarSign },
    rejected: { label: 'Rejected', color: 'bg-red-500', icon: XCircle },
    cancelled: { label: 'Cancelled', color: 'bg-red-500', icon: XCircle },
  };
  
  const config = configs[status] || configs.draft;
  const Icon = config.icon;
  
  return (
    <Badge className={`${config.color} gap-1`}>
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
};

const VehicleListingCard = ({ listing, onView, onEdit }) => {
  const mainImage = listing.media?.find(m => m.category === 'front')?.url || 
                    listing.media?.[0]?.url;
  
  return (
    <Card className="overflow-hidden hover:shadow-lg transition-shadow">
      <div className="flex">
        {/* Image */}
        <div className="w-48 h-36 bg-slate-100 flex-shrink-0">
          {mainImage ? (
            <SafeImage src={mainImage} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Car className="h-12 w-12 text-slate-300" />
            </div>
          )}
        </div>
        
        {/* Content */}
        <CardContent className="flex-1 p-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-lg">
                {listing.year} {listing.make} {listing.model}
              </h3>
              <p className="text-sm text-slate-500 line-clamp-1">{listing.title}</p>
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onView(listing.id)}>
                  <Eye className="h-4 w-4 mr-2" /> View
                </DropdownMenuItem>
                {listing.status === 'draft' && (
                  <DropdownMenuItem onClick={() => onEdit(listing.id)}>
                    <Edit className="h-4 w-4 mr-2" /> Edit
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          
          <div className="flex items-center gap-4 mt-3">
            {getStatusBadge(listing.status)}
            
            <span className="text-sm text-slate-500">
              VIN: {listing.vin?.slice(-6)}
            </span>
            
            {listing.status === 'active' && (
              <span className="text-sm font-medium text-green-600">
                Current: {formatPrice(listing.current_bid || listing.starting_price)}
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-4 mt-3 text-sm text-slate-500">
            <span className="flex items-center gap-1">
              <Eye className="h-4 w-4" /> {listing.views_count || 0} views
            </span>
            <span className="flex items-center gap-1">
              <TrendingUp className="h-4 w-4" /> {listing.bid_count || 0} bids
            </span>
            <span className="flex items-center gap-1">
              <DollarSign className="h-4 w-4" /> {formatPrice(listing.starting_price)}
            </span>
          </div>
          
          {listing.status === 'rejected' && listing.rejection_reason && (
            <div className="mt-3 p-2 bg-red-50 rounded text-sm text-red-600">
              <AlertTriangle className="h-4 w-4 inline mr-1" />
              {listing.rejection_reason}
            </div>
          )}
        </CardContent>
      </div>
    </Card>
  );
};

const MyVehicleListingsPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token, user } = useAuth();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sellerProfile, setSellerProfile] = useState(null);
  const [activeTab, setActiveTab] = useState('all');

  const fetchData = useCallback(async () => {
    if (!token) {
      navigate('/auth');
      return;
    }
    
    try {
      // Get seller profile
      const sellerResp = await axios.get(`${API}/vehicle-sellers/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSellerProfile(sellerResp.data);
      
      // Get listings
      const listingsResp = await axios.get(`${API}/vehicles/my/listings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setListings(listingsResp.data.listings || []);
      
    } catch (error) {
      if (error.response?.status === 404) {
        toast.error('Please register as a vehicle seller first');
        navigate('/vehicle-auctions/seller/register');
      } else {
        toast.error('Failed to load data');
      }
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filteredListings = listings.filter(listing => {
    if (activeTab === 'all') return true;
    if (activeTab === 'active') return listing.status === 'active';
    if (activeTab === 'pending') return ['draft', 'pending_approval', 'approved'].includes(listing.status);
    if (activeTab === 'ended') return ['ended', 'sold', 'cancelled'].includes(listing.status);
    return true;
  });

  const stats = {
    total: listings.length,
    active: listings.filter(l => l.status === 'active').length,
    pending: listings.filter(l => ['draft', 'pending_approval'].includes(l.status)).length,
    sold: listings.filter(l => l.status === 'sold').length,
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="my-listings-page">
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                {t('vehicleListings.title')}
              </h1>
              <p className="text-slate-500 mt-1">
                {t('vehicleListings.subtitle')}
              </p>
            </div>
            
            <Button 
              onClick={() => navigate('/vehicle-auctions/create')}
              className="gap-2"
              disabled={sellerProfile?.verification_status !== 'approved'}
            >
              <Plus className="h-4 w-4" /> {t('vehicleListings.createVehicle')}
            </Button>
          </div>
          
          {/* Stats */}
          <div className="grid grid-cols-4 gap-4 mt-6">
            <Card>
              <CardContent className="p-4">
                <p className="text-2xl font-bold">{stats.total}</p>
                <p className="text-sm text-slate-500">Total Listings</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-2xl font-bold text-green-600">{stats.active}</p>
                <p className="text-sm text-slate-500">Active Auctions</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
                <p className="text-sm text-slate-500">Pending</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-2xl font-bold text-purple-600">{stats.sold}</p>
                <p className="text-sm text-slate-500">Sold</p>
              </CardContent>
            </Card>
          </div>
          
          {/* Monthly Limit */}
          {sellerProfile && (
            <div className="mt-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg flex items-center justify-between">
              <span className="text-sm text-slate-600">
                Monthly Listings: {sellerProfile.monthly_listing_count} / {sellerProfile.monthly_listing_limit}
              </span>
              <Badge variant="outline">
                {sellerProfile.seller_type === 'dealer' ? 'Licensed Dealer' : 
                 sellerProfile.seller_type === 'auctioneer' ? 'Verified Auctioneer' : 
                 'Private Seller'}
              </Badge>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="all">All ({stats.total})</TabsTrigger>
            <TabsTrigger value="active">Active ({stats.active})</TabsTrigger>
            <TabsTrigger value="pending">Pending ({stats.pending})</TabsTrigger>
            <TabsTrigger value="ended">Ended ({listings.filter(l => ['ended', 'sold'].includes(l.status)).length})</TabsTrigger>
          </TabsList>
          
          <TabsContent value={activeTab} className="mt-6">
            {filteredListings.length === 0 ? (
              <Card className="p-12 text-center">
                <Car className="h-16 w-16 text-slate-300 mx-auto mb-4" />
                <h3 className="text-xl font-semibold mb-2">No Listings Found</h3>
                <p className="text-slate-500 mb-6">
                  {activeTab === 'all' 
                    ? "You haven&apos;t created any vehicle listings yet."
                    : `No ${activeTab} listings.`
                  }
                </p>
                {sellerProfile?.verification_status === 'approved' && (
                  <Button onClick={() => navigate('/vehicle-auctions/create')}>
                    <Plus className="h-4 w-4 mr-2" /> Create Your First Listing
                  </Button>
                )}
              </Card>
            ) : (
              <div className="space-y-4">
                {filteredListings.map((listing) => (
                  <VehicleListingCard
                    key={listing.id}
                    listing={listing}
                    onView={(id) => navigate(`/vehicle-auctions/${id}`)}
                    onEdit={(id) => navigate(`/vehicle-auctions/edit/${id}`)}
                  />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default MyVehicleListingsPage;
